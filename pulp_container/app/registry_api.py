"""
Check `Plugin Writer's Guide`_ for more details.

. _Plugin Writer's Guide:
    http://docs.pulpproject.org/plugins/plugin-writer/index.html
"""
import base64
import binascii
import json
import logging
import hashlib
import re
import time

from collections import namedtuple

from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from tempfile import NamedTemporaryFile

from django.core.files.storage import default_storage as storage
from django.core.files.base import ContentFile, File
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404

from django.conf import settings

from pulpcore.plugin.models import Artifact, ContentArtifact, Task, UploadChunk
from pulpcore.plugin.files import PulpTemporaryUploadedFile
from pulpcore.plugin.tasking import add_and_remove, dispatch
from pulpcore.plugin.util import get_objects_for_user
from rest_framework.authentication import BasicAuthentication
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
    ParseError,
    Throttled,
    ValidationError,
)
from rest_framework.generics import ListAPIView
from rest_framework.pagination import BasePagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import BaseRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.serializers import ModelSerializer
from rest_framework.settings import api_settings
from rest_framework.viewsets import ViewSet
from rest_framework.views import APIView

from pulp_container.app import models, serializers
from pulp_container.app.access_policy import RegistryAccessPolicy
from pulp_container.app.authorization import AuthorizationService
from pulp_container.app.cache import find_base_path_cached, RegistryApiCache
from pulp_container.app.exceptions import (
    InvalidRequest,
    RepositoryNotFound,
    RepositoryInvalid,
    BlobNotFound,
    BlobInvalid,
    ManifestNotFound,
    ManifestInvalid,
    ManifestSignatureInvalid,
)
from pulp_container.app.redirects import (
    FileStorageRedirects,
    S3StorageRedirects,
    AzureStorageRedirects,
)
from pulp_container.app.token_verification import (
    RegistryAuthentication,
    TokenAuthentication,
    RegistryPermission,
    TokenPermission,
)
from pulp_container.app.utils import (
    determine_media_type,
    extract_data_from_signature,
    has_task_completed,
    validate_manifest,
)
from pulp_container.constants import (
    EMPTY_BLOB,
    SIGNATURE_API_EXTENSION_VERSION,
    SIGNATURE_HEADER,
    SIGNATURE_PAYLOAD_MAX_SIZE,
    SIGNATURE_TYPE,
)

FakeView = namedtuple("FakeView", ["action", "get_object"])

log = logging.getLogger(__name__)


class ContentRenderer(BaseRenderer):
    """
    Rendered class for rendering Manifest and Blob responses.
    """

    media_type = "*/*"
    format = "txt"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        """Encodes the response data."""
        return data


class UploadResponse(Response):
    """
    An HTTP response class for requests for Uploads.

    This response object provides information about Uploads during 'push' operations.
    """

    def __init__(self, upload, path, request, status=202):
        """
        Args:
            upload (pulp_container.app.models.Upload): An Upload model used to generate the
                response.
            path (str): The base_path of the ContainerDistribution (Container repository name)
            request (rest_framework.request.Request): Request object not used by this
                implementation of Response.
        """
        if upload.size == 0:
            offset = 0
        else:
            offset = int(upload.size - 1)
        headers = {
            "Docker-Upload-UUID": upload.pk,
            "Location": f"/v2/{path}/blobs/uploads/{upload.pk}",
            "Range": "0-{offset}".format(offset=offset),
            "Content-Length": 0,
        }
        super().__init__(headers=headers, status=status)


class ManifestResponse(Response):
    """
    An HTTP response class for returning Manifets.
    """

    def __init__(self, manifest, path, request, status=200):
        """
        Args:
            manifest (pulp_container.app.models.Manifest): A Manifest model used to generate the
                response.
            path (str): The base_path of the ContainerDistribution (Container repository name)
            request (rest_framework.request.Request): Request object not used by this
                implementation of Response.
            status (int): Status code to send with the response.
        """
        headers = {
            "Docker-Content-Digest": manifest.digest,
            "Location": "/v2/{path}/manifests/{digest}".format(path=path, digest=manifest.digest),
            "Content-Length": 0,
        }
        super().__init__(headers=headers, status=status, content_type=manifest.media_type)


class ManifestSignatureResponse(Response):
    """
    An HTTP response class after creating an image signature.
    """

    def __init__(self, signature, path, status=201):
        """Initialize the headers with the path to the repository and corresponding digests."""
        headers = {
            "Location": "/extensions/v2/{path}/signatures/{digest}".format(
                path=path, digest=signature.signed_manifest.digest
            ),
            "Content-Length": 0,
        }
        super().__init__(headers=headers, status=status)


class BlobResponse(Response):
    """
    An HTTP response class for returning Blobs.
    """

    def __init__(self, blob, path, status, request):
        """
        Args:
            blob (pulp_container.app.models.Blob): A Blob model used to generate the response.
            path (str): The base_path of the ContainerDistribution (Container repository name)
            request (rest_framework.request.Request): Request object not used by this
                implementation of Response.
            status (int): Status code to send with the response.
        """
        headers = {
            "Docker-Content-Digest": blob.digest,
            "Location": "/v2/{path}/blobs/{digest}".format(path=path, digest=blob.digest),
            "Content-Length": 0,
        }
        super().__init__(headers=headers, status=status)


class ContainerRegistryApiMixin:
    """
    Mixin to add docker registry specifics to APIView classes.

    This must be inherited from first to gain precedence.
    It adds a registry version header to all responses.
    It sets token authentication and token permission.
    """

    schema = None
    TOKEN_ERROR_CODES = ("invalid_token", "insufficient_scope")

    @property
    def authentication_classes(self):
        """
        List of authentication classes to check for this view.
        """
        if settings.get("TOKEN_AUTH_DISABLED", False):
            return [RegistryAuthentication]
        return [TokenAuthentication]

    @property
    def permission_classes(self):
        """
        List of permission classes to check for this view.
        """
        if settings.get("TOKEN_AUTH_DISABLED", False):
            return [RegistryPermission]
        return [TokenPermission]

    @property
    def default_response_headers(self):
        """
        Provide common headers to all responses.
        """
        headers = super().default_response_headers
        headers.update({"Docker-Distribution-Api-Version": "registry/2.0", SIGNATURE_HEADER: "1"})
        return headers

    def get_exception_handler_context(self):
        """
        Adjust the reder context for exceptions.
        """
        context = super().get_exception_handler_context()
        if context["request"]:
            context["request"].accepted_renderer = JSONRenderer()
            context["request"].accepted_media_type = JSONRenderer.media_type
        return context

    def handle_exception(self, exc):
        """Convert the exception detail to the container api format."""
        detail = getattr(exc, "detail", "")
        # If detail is a dict, we assume the exception meets the required stucture already
        if not isinstance(detail, dict):
            if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
                code = "UNAUTHORIZED"
            elif isinstance(exc, PermissionDenied):
                code = "DENIED"
            else:
                code = "UNSUPPORTED"
            exc.detail = {"errors": [{"code": code, "message": detail, "detail": {}}]}

        response = super().handle_exception(exc)

        # the auth header is available when the response object is initialized
        error_code = getattr(detail, "code", "")
        if error_code in self.TOKEN_ERROR_CODES:
            response["Www-Authenticate"] += f',error="{error_code}"'

        return response

    def get_drv_pull(self, path):
        """
        Get distribution, repository and repository_version for pull access.
        """
        try:
            distribution = models.ContainerDistribution.objects.get(base_path=path)
        except models.ContainerDistribution.DoesNotExist:
            raise RepositoryNotFound(name=path)
        if distribution.repository:
            repository_version = distribution.repository.latest_version()
        elif distribution.repository_version:
            repository_version = distribution.repository_version
        else:
            raise RepositoryNotFound(name=path)
        return distribution, distribution.repository, repository_version

    def get_dr_push(self, request, path, create=False):
        """
        Get distribution and repository for push access.

        Optionally create them if not found.
        """
        try:
            distribution = models.ContainerDistribution.objects.get(base_path=path)
        except models.ContainerDistribution.DoesNotExist:
            if create:
                try:
                    with transaction.atomic():
                        repo_serializer = serializers.ContainerPushRepositorySerializer(
                            data={"name": path}, context={"request": request}
                        )
                        repo_serializer.is_valid(raise_exception=True)
                        repository = repo_serializer.create(repo_serializer.validated_data)
                        repo_href = serializers.ContainerPushRepositorySerializer(
                            repository, context={"request": request}
                        ).data["pulp_href"]

                        dist_serializer = serializers.ContainerDistributionSerializer(
                            data={"base_path": path, "name": path, "repository": repo_href}
                        )
                        dist_serializer.is_valid(raise_exception=True)
                        distribution = dist_serializer.create(dist_serializer.validated_data)
                except ValidationError:
                    raise RepositoryInvalid(name=path)
                except IntegrityError:
                    # Seems like another process created our stuff already. Retry fetching it.
                    distribution = models.ContainerDistribution.objects.get(base_path=path)
                    repository = distribution.repository
                    if repository:
                        repository = repository.cast()
                        if not repository.PUSH_ENABLED:
                            raise RepositoryInvalid(name=path, message="Repository is read-only.")
            else:
                raise RepositoryNotFound(name=path)
        else:
            repository = distribution.repository
            if repository:
                repository = repository.cast()
                if not repository.PUSH_ENABLED:
                    raise RepositoryInvalid(name=path, message="Repository is read-only.")
            elif create:
                try:
                    with transaction.atomic():
                        repo_serializer = serializers.ContainerPushRepositorySerializer(
                            data={"name": path}, context={"request": request}
                        )
                        repo_serializer.is_valid(raise_exception=True)
                        repository = repo_serializer.create(repo_serializer.validated_data)
                        distribution.repository = repository
                        distribution.save()
                except IntegrityError:
                    # Seems like another process created our stuff already. Retry fetching it.
                    distribution = models.ContainerDistribution.objects.get(pk=distribution.pk)
                    repository = distribution.repository
                    if repository:
                        repository = repository.cast()
                        if not repository.PUSH_ENABLED:
                            raise RepositoryInvalid(name=path, message="Repository is read-only.")
                    else:
                        raise RepositoryNotFound(name=path)
            else:
                raise RepositoryNotFound(name=path)
        return distribution, repository


class BearerTokenView(APIView):
    """
    Hand out anonymous or authenticated bearer tokens.
    """

    # Allow everyone to access but still value authenticated users.
    authentication_classes = [BasicAuthentication]
    permission_classes = []

    def get(self, request):
        """Handles GET requests for the /token/ endpoint."""
        try:
            service = request.query_params["service"]
        except KeyError:
            raise ParseError(detail="No service name provided.")
        scope = request.query_params.getlist("scope", [])

        authorization_service = AuthorizationService(self.request.user, service, scope)
        data = authorization_service.generate_token()
        return Response(data=data)


class VersionView(ContainerRegistryApiMixin, APIView):
    """
    Handles requests to the /v2/ endpoint.
    """

    @property
    def permission_classes(self):
        """
        List of permission classes to check for this view.
        """
        if settings.get("TOKEN_AUTH_DISABLED", False):
            return [IsAuthenticated]
        return [TokenPermission]

    def get(self, request):
        """Handles GET requests for the /v2/ endpoint."""
        return Response(data={})


class ContainerCatalogSerializer(ModelSerializer):
    """
    Serializer for Distributions in the _catalog endpoint of the registry.
    """

    class Meta:
        model = models.ContainerDistribution
        fields = ["base_path"]


class ContainerCatalogPagination(BasePagination):
    """
    Pagination class to paginate repositories by names according to the registry api specification.
    """

    def paginate_queryset(self, queryset, request, view=None):
        """
        Analyse the pagination parameters and prepare the queryset.
        """
        try:
            self.n = int(request.query_params.get("n"))
        except Exception:
            self.n = api_settings.PAGE_SIZE
        else:
            if self.n > 10 * api_settings.PAGE_SIZE:
                self.n = 10 * api_settings.PAGE_SIZE
            if self.n < 0:
                self.n = 0
        last = request.query_params.get("last")
        self.url = request.build_absolute_uri()

        if last:
            queryset = queryset.filter(base_path__gt=last)
        return queryset.order_by("base_path")[: self.n]

    def get_paginated_response(self, data):
        """
        Prepare the paginated container _catalog response.
        """
        headers = {}
        repositories_names = [repo["base_path"] for repo in data]
        if self.n and len(repositories_names) == self.n:
            # There's a high chance we haven't gotten all entries here.
            parsed_url = list(urlparse(self.url))
            query_params = parse_qs(parsed_url[4])
            query_params["n"] = str(self.n)
            query_params["last"] = repositories_names[-1]
            parsed_url[4] = urlencode(query_params)
            url = urlunparse(parsed_url)
            headers["Link"] = f'<{url}>; rel="next"'
        return Response(headers=headers, data={"repositories": repositories_names})


class CatalogView(ContainerRegistryApiMixin, ListAPIView):
    """
    Handles requests to the /v2/_catalog endpoint
    """

    queryset = models.ContainerDistribution.objects.all().only("base_path")
    serializer_class = ContainerCatalogSerializer
    pagination_class = ContainerCatalogPagination
    access_policy_class = RegistryAccessPolicy()

    def get_queryset(self, *args, **kwargs):
        """Filter the queryset based on public repositories and assigned permissions."""
        queryset = super().get_queryset()

        distribution_permission = "container.pull_containerdistribution"
        namespace_permission = "container.namespace_pull_containerdistribution"

        public_repositories = queryset.filter(private=False)
        repositories_by_distribution = get_objects_for_user(
            self.request.user, distribution_permission, queryset
        )

        namespaces = models.ContainerNamespace.objects.all()
        repositories_by_namespace = get_objects_for_user(
            self.request.user, namespace_permission, namespaces
        )
        repositories_by_namespace = queryset.filter(namespace__in=repositories_by_namespace)

        accessible_repositories = repositories_by_distribution & repositories_by_namespace
        return (public_repositories | accessible_repositories).distinct()


class ContainerTagListSerializer(ModelSerializer):
    """
    Serializer for Tags in the tags list endpoint of the registry.
    """

    class Meta:
        model = models.Tag
        fields = ["name"]


class ContainerTagListPagination(BasePagination):
    """
    Pagination class to paginate tags by names according to the registry api specification.
    """

    def paginate_queryset(self, queryset, request, view=None):
        """
        Analyse the pagination parameters and prepare the queryset.
        """
        try:
            self.n = int(request.query_params.get("n"))
        except Exception:
            self.n = api_settings.PAGE_SIZE
        else:
            if self.n > 10 * api_settings.PAGE_SIZE:
                self.n = 10 * api_settings.PAGE_SIZE
            if self.n < 0:
                self.n = 0
        last = request.query_params.get("last")
        self.url = request.build_absolute_uri()
        self.path = request.resolver_match.kwargs["path"]

        if last:
            queryset = queryset.filter(name__gt=last)
        return queryset.order_by("name")[: self.n]

    def get_paginated_response(self, data):
        """
        Prepare the paginated container _catalog response.
        """
        headers = {}
        tag_names = [tag["name"] for tag in data]
        if self.n and len(tag_names) == self.n:
            # There's a high chance we haven't gotten all entries here.
            parsed_url = list(urlparse(self.url))
            query_params = parse_qs(parsed_url[4])
            query_params["n"] = str(self.n)
            query_params["last"] = tag_names[-1]
            parsed_url[4] = urlencode(query_params)
            url = urlunparse(parsed_url)
            headers["Link"] = f'<{url}>; rel="next"'
        return Response(headers=headers, data={"name": self.path, "tags": tag_names})


class TagsListView(ContainerRegistryApiMixin, ListAPIView):
    """
    Handles requests to the /v2/<repo>/tags/list endpoint
    """

    serializer_class = ContainerTagListSerializer
    pagination_class = ContainerTagListPagination

    def get_queryset(self):
        """
        Handles GET requests to the /v2/<repo>/tags/list endpoint
        """
        path = self.request.resolver_match.kwargs["path"]
        _, _, repository_version = self.get_drv_pull(path)
        return models.Tag.objects.filter(pk__in=repository_version.content).only("name")


class BlobUploads(ContainerRegistryApiMixin, ViewSet):
    """
    The ViewSet for handling uploading of blobs.
    """

    model = models.Upload
    queryset = models.Upload.objects.all()

    content_range_pattern = re.compile(r"^([0-9]+)-([0-9]+)$")

    def create(self, request, path):
        """
        Create a new upload.

        Note: We do not support monolithic upload.
        """
        _, repository = self.get_dr_push(request, path, create=True)

        if self.tries_to_mount_blob(request):
            response = self.mount_blob(request, path, repository)
        else:
            upload = models.Upload(repository=repository, size=0)
            upload.save()
            response = UploadResponse(upload=upload, path=path, request=request)

        return response

    @staticmethod
    def tries_to_mount_blob(request):
        """Check if a client is trying to perform cross repository blob mounting."""
        return (request.query_params.keys()) == {"from", "mount"}

    def mount_blob(self, request, path, repository):
        """Mount a blob that is already present in another repository."""
        from_path = request.query_params["from"]
        try:
            distribution = models.ContainerDistribution.objects.get(base_path=from_path)
        except models.ContainerDistribution.DoesNotExist:
            raise RepositoryNotFound(name=path)

        try:
            version = distribution.repository_version or distribution.repository.latest_version()
        except AttributeError:
            # the distribution does not contain reference to the source repository version
            raise RepositoryNotFound(name=from_path)

        digest = request.query_params["mount"]
        try:
            blob = models.Blob.objects.get(digest=digest, pk__in=version.content)
        except models.Blob.DoesNotExist:
            raise BlobNotFound(digest=digest)

        dispatched_task = dispatch(
            add_and_remove,
            shared_resources=[version.repository],
            exclusive_resources=[repository],
            kwargs={
                "repository_pk": str(repository.pk),
                "add_content_units": [str(blob.pk)],
                "remove_content_units": [],
            },
        )

        # Wait a small amount of time
        for dummy in range(3):
            time.sleep(1)
            task = Task.objects.get(pk=dispatched_task.pk)
            if task.state == "completed":
                task.delete()
                return BlobResponse(blob, path, 201, request)
            elif task.state in ["waiting", "running"]:
                continue
            else:
                error = task.error
                task.delete()
                raise Exception(str(error))
        raise Throttled()

    def partial_update(self, request, path, pk=None):
        """
        Process a chunk that will be appended to an existing upload.
        """
        _, repository = self.get_dr_push(request, path)
        upload = get_object_or_404(models.Upload, repository=repository, pk=pk)
        chunk = request.META["wsgi.input"]
        if range_header := request.headers.get("Content-Range"):
            found = self.content_range_pattern.match(range_header)
            if not found:
                raise InvalidRequest(message="Invalid range header")
            start = int(found.group(1))
            end = int(found.group(2))
            length = end - start + 1

        else:
            length = int(request.headers.get("Content-Length", 0))
            start = 0

        with transaction.atomic():
            if upload.size != start:
                raise Exception

            # if more chunks
            if range_header:
                chunk = ContentFile(chunk.read())
                upload.append(chunk, upload.size)
            else:
                # 1 chunk
                # do not add to the upload, create artifact right away
                with NamedTemporaryFile("ab") as temp_file:
                    temp_file.write(chunk.read())
                    temp_file.flush()

                    uploaded_file = PulpTemporaryUploadedFile.from_file(
                        File(open(temp_file.name, "rb"))
                    )
                try:
                    artifact = Artifact.init_and_validate(uploaded_file)
                    artifact.save()
                except IntegrityError:
                    artifact = Artifact.objects.get(sha256=artifact.sha256)
                    artifact.touch()
                upload.artifact = artifact
                if not length:
                    length = artifact.size

            upload.size += length
            upload.save()

        return UploadResponse(upload=upload, path=path, request=request, status=204)

    def put(self, request, path, pk=None):
        """
        Create a blob from uploaded chunks.

        Note: We do not support monolithic upload.
        """
        _, repository = self.get_dr_push(request, path)

        digest = request.query_params["digest"]
        # Try to see if the client came back after we told it to backoff with the ``Throttled``
        # exception. In that case we answer based on the task state, or make it backoff again.
        # This mechanism seems to work with podman but not with docker. However we let the task run
        # anyway, since all clients will look with a HEAD request before attemting to upload a blob
        # again.
        try:
            upload = models.Upload.objects.get(pk=pk, repository=repository)
        except models.Upload.DoesNotExist as e_upload:
            # Upload has been deleted => task has started or even finished
            task = Task.objects.filter(
                name__endswith="add_and_remove",
                reserved_resources_record__contains=[f"shared:upload:{pk}"],
            ).last()
            if not task:
                # No upload and no task for it => the upload probably never existed
                # return 404
                raise e_upload

            if task.state == "completed":
                task.delete()
                blob = models.Blob.objects.get(digest=digest)
                return BlobResponse(blob, path, 201, request)
            elif task.state in ["waiting", "running"]:
                raise Throttled()
            else:
                error = task.error
                task.delete()
                raise Exception(str(error))

        if artifact := upload.artifact:
            if artifact.sha256 != digest[len("sha256:") :]:
                raise Exception("The digest did not match")
            artifact.touch()
        else:
            chunks = UploadChunk.objects.filter(upload=upload).order_by("offset")
            with NamedTemporaryFile("ab") as temp_file:
                for chunk in chunks:
                    temp_file.write(chunk.file.read())
                    chunk.file.close()
                temp_file.flush()

                uploaded_file = PulpTemporaryUploadedFile.from_file(
                    File(open(temp_file.name, "rb"))
                )
            if uploaded_file.hashers["sha256"].hexdigest() != digest[len("sha256:") :]:
                upload.delete()
                raise Exception("The digest did not match")
            try:
                artifact = Artifact.init_and_validate(uploaded_file)
                artifact.save()
            except IntegrityError:
                artifact = Artifact.objects.get(sha256=artifact.sha256)
                artifact.touch()

        with transaction.atomic():
            try:
                blob = models.Blob(digest=digest)
                blob.save()
            except IntegrityError:
                blob = models.Blob.objects.get(digest=digest)
                blob.touch()
            try:
                blob_artifact = ContentArtifact(
                    artifact=artifact, content=blob, relative_path=digest
                )
                blob_artifact.save()
            except IntegrityError:
                ca = ContentArtifact.objects.get(content=blob, relative_path=digest)
                if not ca.artifact:
                    ca.artifact = artifact
                    ca.save(update_fields=["artifact"])
        upload.delete()

        dispatched_task = dispatch(
            add_and_remove,
            shared_resources=[f"upload:{pk}"],
            exclusive_resources=[repository],
            kwargs={
                "repository_pk": str(repository.pk),
                "add_content_units": [str(blob.pk)],
                "remove_content_units": [],
            },
        )

        if has_task_completed(dispatched_task):
            return BlobResponse(blob, path, 201, request)


class RedirectsMixin:
    """
    A mixin used for configuring how the redirects will work based on a storage type.
    """

    def __init__(self, *args, **kwargs):
        """
        Determine a storage type and initialize the redirect class according to that.
        """
        super().__init__(*args, **kwargs)

        if (
            settings.DEFAULT_FILE_STORAGE == "pulpcore.app.models.storage.FileSystem"
            or not settings.REDIRECT_TO_OBJECT_STORAGE
        ):
            self.redirects_class = FileStorageRedirects
        elif settings.DEFAULT_FILE_STORAGE == "storages.backends.s3boto3.S3Boto3Storage":
            self.redirects_class = S3StorageRedirects
        elif settings.DEFAULT_FILE_STORAGE == "storages.backends.azure_storage.AzureStorage":
            self.redirects_class = AzureStorageRedirects
        else:
            raise NotImplementedError()


class Blobs(RedirectsMixin, ContainerRegistryApiMixin, ViewSet):
    """
    ViewSet for interacting with Blobs
    """

    renderer_classes = [ContentRenderer]

    def head(self, request, path, pk=None):
        """
        Responds to HEAD requests about blobs
        """
        return self.handle_safe_method(request, path, pk=pk)

    def get(self, request, path, pk):
        """
        Responds to GET requests about blobs
        """
        return self.handle_safe_method(request, path, pk)

    @RegistryApiCache(base_key=lambda req, cac: find_base_path_cached(req, cac))
    def handle_safe_method(self, request, path, pk):
        """Handles safe requests for Blobs."""
        distribution, _, repository_version = self.get_drv_pull(path)
        redirects = self.redirects_class(distribution, path, request)

        try:
            blob = models.Blob.objects.get(digest=pk, pk__in=repository_version.content)
        except models.Blob.DoesNotExist:
            if pk == EMPTY_BLOB:
                return redirects.redirect_to_content_app("blobs", pk)
            raise BlobNotFound(digest=pk)
        return redirects.issue_blob_redirect(blob)


class Manifests(RedirectsMixin, ContainerRegistryApiMixin, ViewSet):
    """
    ViewSet for interacting with Manifests
    """

    renderer_classes = [ContentRenderer]
    # The lookup regex does not allow /, ^, &, *, %, !, ~, @, #, +, =, ?
    lookup_value_regex = "[^/^&*%!~@#+=?]+"

    def head(self, request, path, pk=None):
        """
        Responds to HEAD requests about manifests by reference
        """
        return self.handle_safe_method(request, path, pk=pk)

    def get(self, request, path, pk):
        """
        Responds to GET requests about manifests by reference
        """
        return self.handle_safe_method(request, path, pk)

    @RegistryApiCache(base_key=lambda req, cac: find_base_path_cached(req, cac))
    def handle_safe_method(self, request, path, pk):
        """
        Responds to safe requests about manifests by reference
        """
        distribution, _, repository_version = self.get_drv_pull(path)
        redirects = self.redirects_class(distribution, path, request)

        try:
            if pk[:7] != "sha256:":
                tag = models.Tag.objects.get(name=pk, pk__in=repository_version.content)
                return redirects.issue_tag_redirect(tag)
            else:
                manifest = models.Manifest.objects.get(digest=pk, pk__in=repository_version.content)
        except (models.Tag.DoesNotExist, models.Manifest.DoesNotExist):
            raise ManifestNotFound(reference=pk)

        return redirects.issue_manifest_redirect(manifest)

    def put(self, request, path, pk=None):
        """
        Responds with the actual manifest
        """
        # iterate over all the layers and create
        chunk = request.META["wsgi.input"]
        artifact = self.receive_artifact(chunk)
        manifest_digest = "sha256:{id}".format(id=artifact.sha256)

        with storage.open(artifact.file.name) as artifact_file:
            raw_data = artifact_file.read()

        content_data = json.loads(raw_data)

        media_type = determine_media_type(content_data, request)
        validate_manifest(content_data, media_type, manifest_digest)

        # when a user uploads a manifest list with zero listed manifests (no blobs were uploaded
        # before) and the specified repository has not been created yet, create the repository
        # without raising an error
        create_new_repo = media_type in (
            models.MEDIA_TYPE.MANIFEST_LIST,
            models.MEDIA_TYPE.INDEX_OCI,
        )
        _, repository = self.get_dr_push(request, path, create=create_new_repo)

        if media_type in (
            models.MEDIA_TYPE.MANIFEST_LIST,
            models.MEDIA_TYPE.INDEX_OCI,
        ):
            manifests = {}
            for manifest in content_data.get("manifests"):
                manifests[manifest["digest"]] = manifest["platform"]

            digests = set(manifests.keys())
            found_manifests = models.Manifest.objects.filter(digest__in=digests)

            if (len(manifests) - found_manifests.count()) != 0:
                ManifestInvalid(digest=manifest_digest)

            manifest_list = self._save_manifest(artifact, manifest_digest, media_type)

            manifests_to_list = []
            for manifest in found_manifests:
                platform = manifests[manifest.digest]
                manifest_to_list = models.ManifestListManifest(
                    manifest_list=manifest,
                    image_manifest=manifest_list,
                    architecture=platform["architecture"],
                    os=platform["os"],
                    features=platform.get("features", ""),
                    variant=platform.get("variant", ""),
                    os_version=platform.get("os.version", ""),
                    os_features=platform.get("os.features", ""),
                )
                manifests_to_list.append(manifest_to_list)

            models.ManifestListManifest.objects.bulk_create(
                manifests_to_list, ignore_conflicts=True, batch_size=1000
            )
            manifest = manifest_list
        else:
            # both docker/oci format should contain config, digest, mediaType, size
            config_layer = content_data.get("config")
            if not config_layer:
                raise ManifestInvalid(
                    digest=manifest_digest,
                    reason="Pushing manifests of the version V1 is not supported",
                )

            config_digest = config_layer.get("digest")
            try:
                config_blob = models.Blob.objects.get(
                    digest=config_digest, pk__in=repository.latest_version().content
                )
            except models.Blob.DoesNotExist:
                raise BlobInvalid(digest=config_digest)

            # both docker/oci format should contain layers, digest, media_type, size
            layers = content_data.get("layers")
            blobs = set()
            for layer in layers:
                layer_media_type = layer.get("mediaType")
                urls = layer.get("urls")
                if (
                    layer_media_type
                    in (
                        models.MEDIA_TYPE.FOREIGN_BLOB,
                        models.MEDIA_TYPE.FOREIGN_BLOB_OCI_TAR,
                        models.MEDIA_TYPE.FOREIGN_BLOB_OCI_TAR_GZIP,
                        models.MEDIA_TYPE.FOREIGN_BLOB_OCI_TAR_ZSTD,
                    )
                    and not urls
                ):
                    raise ManifestInvalid(
                        digest=manifest_digest,
                        reason="The URL of a foreign layer must be specified",
                    )

                digest = layer.get("digest")
                blobs.add(digest)

            blobs_qs = models.Blob.objects.filter(
                digest__in=blobs, pk__in=repository.latest_version().content
            )
            if (len(blobs) - blobs_qs.count()) != 0:
                raise ManifestInvalid(digest=manifest_digest)

            manifest = self._save_manifest(artifact, manifest_digest, media_type, config_blob)

            thru = []
            for blob in blobs_qs:
                thru.append(models.BlobManifest(manifest=manifest, manifest_blob=blob))
            models.BlobManifest.objects.bulk_create(
                objs=thru, ignore_conflicts=True, batch_size=1000
            )

        # a manifest cannot tagged by its digest - an identifier specified in the 'pk' parameter
        if not pk.startswith("sha256:"):
            tag = models.Tag(name=pk, tagged_manifest=manifest)
            try:
                tag.save()
            except IntegrityError:
                tag = models.Tag.objects.get(name=tag.name, tagged_manifest=manifest)
                tag.touch()

            tags_to_remove = models.Tag.objects.filter(
                pk__in=repository.latest_version().content.all(), name=tag
            ).exclude(tagged_manifest=manifest)
            add_content_units = [str(tag.pk), str(manifest.pk)]
            remove_content_units = [str(pk) for pk in tags_to_remove.values_list("pk")]
        else:
            add_content_units = [str(manifest.pk)]
            remove_content_units = []

        dispatched_task = dispatch(
            add_and_remove,
            exclusive_resources=[repository],
            kwargs={
                "repository_pk": str(repository.pk),
                "add_content_units": add_content_units,
                "remove_content_units": remove_content_units,
            },
        )

        if has_task_completed(dispatched_task):
            return ManifestResponse(manifest, path, request, status=201)

    def _save_manifest(self, artifact, manifest_digest, content_type, config_blob=None):
        manifest = models.Manifest(
            digest=manifest_digest,
            schema_version=2,
            media_type=content_type,
            config_blob=config_blob,
        )
        try:
            manifest.save()
        except IntegrityError:
            manifest = models.Manifest.objects.get(digest=manifest.digest)
            manifest.touch()
        ca = ContentArtifact(artifact=artifact, content=manifest, relative_path=manifest.digest)
        try:
            ca.save()
        except IntegrityError:
            ca = ContentArtifact.objects.get(content=manifest, relative_path=manifest.digest)
            if not ca.artifact:
                ca.artifact = artifact
                ca.save(update_fields=["artifact"])
        return manifest

    def receive_artifact(self, chunk):
        """Handles assembling of Manifest as it's being uploaded."""
        with NamedTemporaryFile("ab") as temp_file:
            size = 0
            hashers = {}
            for algorithm in Artifact.DIGEST_FIELDS:
                hashers[algorithm] = getattr(hashlib, algorithm)()
            while True:
                subchunk = chunk.read(2000000)
                if not subchunk:
                    break
                temp_file.write(subchunk)
                size += len(subchunk)
                for algorithm in Artifact.DIGEST_FIELDS:
                    hashers[algorithm].update(subchunk)
            temp_file.flush()
            digests = {}
            for algorithm in Artifact.DIGEST_FIELDS:
                digests[algorithm] = hashers[algorithm].hexdigest()
            artifact = Artifact(file=temp_file.name, size=size, **digests)
            try:
                artifact.save()
            except IntegrityError:
                artifact = Artifact.objects.get(sha256=artifact.sha256)
                artifact.touch()
            return artifact


class Signatures(ContainerRegistryApiMixin, ViewSet):
    """A ViewSet for image signatures."""

    lookup_value_regex = "sha256:[0-9a-f]{64}"

    def head(self, request, path, pk=None):
        """Respond to HEAD requests querying signatures by sha256."""
        return self.get(request, path, pk=pk)

    def get(self, request, path, pk):
        """Return a signature identified by its sha256 checksum."""
        _, _, repository_version = self.get_drv_pull(path)

        try:
            manifest = models.Manifest.objects.get(digest=pk, pk__in=repository_version.content)
        except models.Manifest.DoesNotExist:
            raise ManifestNotFound(reference=pk)

        signatures = models.ManifestSignature.objects.filter(
            signed_manifest=manifest, pk__in=repository_version.content
        )

        return Response(self.get_response_data(signatures))

    @staticmethod
    def get_response_data(signatures):
        """Extract version, type, name, and content from the passed signature data."""
        data = []
        for signature in signatures:
            signature = {
                "schemaVersion": SIGNATURE_API_EXTENSION_VERSION,
                "type": signature.type,
                "name": signature.name,
                "content": signature.data,
            }
            data.append(signature)
        return {"signatures": data}

    def put(self, request, path, pk):
        """Create a new signature from the received data."""
        _, repository = self.get_dr_push(request, path)

        try:
            manifest = models.Manifest.objects.get(
                digest=pk, pk__in=repository.latest_version().content
            )
        except models.Manifest.DoesNotExist:
            raise ManifestNotFound(reference=pk)

        signature_payload = request.META["wsgi.input"].read(SIGNATURE_PAYLOAD_MAX_SIZE)
        try:
            signature_dict = json.loads(signature_payload)
        except json.decoder.JSONDecodeError:
            raise ManifestSignatureInvalid(digest=pk)

        serializer = serializers.ManifestSignaturePutSerializer(data=signature_dict)
        serializer.is_valid(raise_exception=True)

        try:
            signature_raw = base64.b64decode(signature_dict["content"])
        except binascii.Error:
            raise ManifestSignatureInvalid(digest=pk)

        signature_json = extract_data_from_signature(signature_raw, manifest.digest)
        if signature_json is None:
            raise ManifestSignatureInvalid(digest=pk)

        sig_digest = hashlib.sha256(signature_raw).hexdigest()
        signature = models.ManifestSignature(
            name=f"{manifest.digest}@{sig_digest[:32]}",
            digest=f"sha256:{sig_digest}",
            type=SIGNATURE_TYPE.ATOMIC_SHORT,
            key_id=signature_json["signing_key_id"],
            timestamp=signature_json["signature_timestamp"],
            creator=signature_json["optional"].get("creator"),
            data=signature_dict["content"],
            signed_manifest=manifest,
        )
        try:
            signature.save()
        except IntegrityError:
            signature = models.ManifestSignature.objects.get(digest=signature.digest)
            signature.touch()

        dispatched_task = dispatch(
            add_and_remove,
            exclusive_resources=[repository],
            kwargs={
                "repository_pk": str(repository.pk),
                "add_content_units": [str(signature.pk)],
                "remove_content_units": [],
            },
        )

        if has_task_completed(dispatched_task):
            return ManifestSignatureResponse(signature, path)

"""
Check `Plugin Writer's Guide`_ for more details.

. _Plugin Writer's Guide:
    http://docs.pulpproject.org/plugins/plugin-writer/index.html
"""
import json
import logging
import hashlib
import re
from collections import namedtuple
import time

from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from tempfile import NamedTemporaryFile

from django.core.files.storage import default_storage as storage
from django.core.files.base import ContentFile, File
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404

from django.conf import settings

from guardian.shortcuts import get_objects_for_user

from pulpcore.plugin.models import Artifact, ContentArtifact, Task, UploadChunk
from pulpcore.plugin.files import PulpTemporaryUploadedFile
from pulpcore.plugin.tasking import add_and_remove, enqueue_with_reservation
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
    NotFound,
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
from pulp_container.app.redirects import FileStorageRedirects, S3StorageRedirects
from pulp_container.app.token_verification import (
    RegistryAuthentication,
    TokenAuthentication,
    RegistryPermission,
    TokenPermission,
)

FakeView = namedtuple("FakeView", ["action", "get_object"])

log = logging.getLogger(__name__)


class RepositoryNotFound(NotFound):
    """Exception to render a 404 with the code 'NAME_UNKNOWN'"""

    def __init__(self, name):
        """Initialize the exception with the repository name."""
        super().__init__(
            detail={
                "errors": [
                    {
                        "code": "NAME_UNKNOWN",
                        "message": "Repository not found.",
                        "detail": {"name": name},
                    }
                ]
            }
        )


class RepositoryInvalid(ParseError):
    """Exception to render a 400 with the code 'NAME_INVALID'"""

    def __init__(self, name, message=None):
        """Initialize the exception with the repository name."""
        message = message or "Invalid repository name."
        super().__init__(
            detail={
                "errors": [{"code": "NAME_INVALID", "message": message, "detail": {"name": name}}]
            }
        )


class BlobNotFound(NotFound):
    """Exception to render a 404 with the code 'BLOB_UNKNOWN'"""

    def __init__(self, digest):
        """Initialize the exception with the blob digest."""
        super().__init__(
            detail={
                "errors": [
                    {
                        "code": "BLOB_UNKNOWN",
                        "message": "Blob not found.",
                        "detail": {"digest": digest},
                    }
                ]
            }
        )


class ManifestNotFound(NotFound):
    """Exception to render a 404 with the code 'MANIFEST_UNKNOWN'"""

    def __init__(self, reference):
        """Initialize the exception with the manifest reference."""
        super().__init__(
            detail={
                "errors": [
                    {
                        "code": "MANIFEST_UNKNOWN",
                        "message": "Manifest not found.",
                        "detail": {"reference": reference},
                    }
                ]
            }
        )


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

    def __init__(self, upload, path, content_length, request):
        """
        Args:
            upload (pulp_container.app.models.Upload): An Upload model used to generate the
                response.
            path (str): The base_path of the ContainerDistribution (Container repository name)
            content_length (int): The value for the Content-Length header.
            request (rest_framework.request.Request): Request object not used by this
                implementation of Response.
        """
        headers = {
            "Docker-Upload-UUID": upload.pk,
            "Location": f"/v2/{path}/blobs/uploads/{upload.pk}",
            "Range": "0-{offset}".format(offset=int(upload.size - 1)),
            "Content-Length": content_length,
        }
        super().__init__(headers=headers, status=202)


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
        artifact = manifest._artifacts.get()
        size = artifact.size
        headers = {
            "Docker-Content-Digest": manifest.digest,
            "Location": "/v2/{path}/manifests/{digest}".format(path=path, digest=manifest.digest),
            "Content-Length": size,
        }
        super().__init__(headers=headers, status=status, content_type=manifest.media_type)


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
        artifact = blob._artifacts.get()
        size = artifact.size

        headers = {
            "Docker-Content-Digest": blob.digest,
            "Location": "/v2/{path}/blobs/{digest}".format(path=path, digest=blob.digest),
            "Etag": blob.digest,
            "Range": "0-{offset}".format(offset=int(size)),
            "Content-Length": size,
            "Content-Type": "application/octet-stream",
            "Connection": "close",
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
        headers.update({"Docker-Distribution-Api-Version": "registry/2.0"})
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
    permission_classes = []

    def get(self, request):
        """Handles GET requests for the /token/ endpoint."""
        try:
            service = request.query_params["service"]
        except KeyError:
            raise ParseError(detail="No service name provided.")
        scope = request.query_params.get("scope", "")

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

        namespace_refs = queryset.values_list("namespace", flat=True)
        namespaces = models.ContainerNamespace.objects.filter(pk__in=namespace_refs)
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

    content_range_pattern = re.compile(r"^(?P<start>\d+)-(?P<end>\d+)$")

    def create(self, request, path):
        """
        Create a new upload.
        """
        _, repository = self.get_dr_push(request, path, create=True)

        upload = models.Upload(repository=repository, size=0)
        upload.save()
        response = UploadResponse(upload=upload, path=path, content_length=0, request=request)

        return response

    def partial_update(self, request, path, pk=None):
        """
        Process a chunk that will be appended to an existing upload.
        """
        _, repository = self.get_dr_push(request, path)
        chunk = request.META["wsgi.input"]
        if "Content-Range" in request.headers or "digest" not in request.query_params:
            whole = False
        else:
            whole = True

        if whole:
            start = 0
        else:
            content_range = request.META.get("HTTP_CONTENT_RANGE", "")
            match = self.content_range_pattern.match(content_range)
            start = 0 if not match else int(match.group("start"))

        upload = get_object_or_404(models.Upload, repository=repository, pk=pk)

        chunk = ContentFile(chunk.read())
        with transaction.atomic():
            if upload.size != start:
                raise Exception

            upload.append(chunk, upload.size)
            upload.size += chunk.size
            upload.save()

        return UploadResponse(upload=upload, path=path, content_length=chunk.size, request=request)

    def put(self, request, path, pk=None):
        """
        Create a blob from uploaded chunks.
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
            try:
                task = Task.objects.filter(
                    name__endswith="add_and_remove",
                    reserved_resources_record__resource=f"upload:{pk}",
                ).last()
            except Task.DoesNotExist:
                # No upload and no task for it => the upload probably never existed
                # return 404
                raise e_upload

            if task.state == "completed":
                task.delete()
                blob = models.Blob.objects.get(digest=digest)
                return BlobResponse(blob, path, 201, request)
            elif task.state in ["waiting", "running"]:
                raise Throttled(wait=5)
            else:
                task.delete()
                raise Exception("Failed.")

        chunks = UploadChunk.objects.filter(upload=upload).order_by("offset")

        with NamedTemporaryFile("ab") as temp_file:
            for chunk in chunks:
                temp_file.write(chunk.file.read())
            temp_file.flush()

            uploaded_file = PulpTemporaryUploadedFile.from_file(File(open(temp_file.name, "rb")))

        if uploaded_file.hashers["sha256"].hexdigest() == digest[len("sha256:") :]:
            try:
                artifact = Artifact.init_and_validate(uploaded_file)
                artifact.save()
            except IntegrityError:
                artifact = Artifact.objects.get(sha256=artifact.sha256)
            try:
                blob = models.Blob(digest=digest, media_type=models.MEDIA_TYPE.REGULAR_BLOB)
                blob.save()
            except IntegrityError:
                blob = models.Blob.objects.get(digest=digest)
            try:
                blob_artifact = ContentArtifact(
                    artifact=artifact, content=blob, relative_path=digest
                )
                blob_artifact.save()
            except IntegrityError:
                pass

            upload.delete()

            job = enqueue_with_reservation(
                add_and_remove,
                [f"upload:{pk}", repository],
                kwargs={
                    "repository_pk": repository.pk,
                    "add_content_units": [blob.pk],
                    "remove_content_units": [],
                },
            )

            # Wait a small amount of time
            for dummy in range(3):
                time.sleep(1)
                task = Task.objects.get(pk=job.id)
                if task.state == "completed":
                    task.delete()
                    return BlobResponse(blob, path, 201, request)
                elif task.state in ["waiting", "running"]:
                    continue
                else:
                    task.delete()
                    raise Exception("Failed.")
            raise Throttled(wait=5)
        else:
            raise Exception("The digest did not match")


class RedirectsMixin:
    """
    A mixin used for configuring how the redirects will work based on a storage type.
    """

    def __init__(self, *args, **kwargs):
        """
        Determine a storage type and initialize the redirect class according to that.
        """
        super().__init__(*args, **kwargs)

        if settings.DEFAULT_FILE_STORAGE == "pulpcore.app.models.storage.FileSystem":
            self.redirects_class = FileStorageRedirects
        elif settings.DEFAULT_FILE_STORAGE == "storages.backends.s3boto3.S3Boto3Storage":
            self.redirects_class = S3StorageRedirects
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
        return self.get(request, path, pk=pk)

    def get(self, request, path, pk=None):
        """Handles GET requests for Blobs."""
        distribution, _, repository_version = self.get_drv_pull(path)
        redirects = self.redirects_class(distribution, path, request)

        try:
            blob = models.Blob.objects.get(digest=pk, pk__in=repository_version.content)
        except models.Blob.DoesNotExist:
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

        return self.get(request, path, pk=pk)

    def get(self, request, path, pk=None):
        """
        Responds to GET requests about manifests by reference
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
        _, repository = self.get_dr_push(request, path)
        # iterate over all the layers and create
        chunk = request.META["wsgi.input"]
        artifact = self.receive_artifact(chunk)
        with storage.open(artifact.file.name) as artifact_file:
            raw_data = artifact_file.read()
        content_data = json.loads(raw_data)
        config_layer = content_data.get("config")
        config_blob = models.Blob.objects.get(digest=config_layer.get("digest"))

        manifest = models.Manifest(
            digest="sha256:{id}".format(id=artifact.sha256),
            schema_version=2,
            media_type=request.content_type,
            config_blob=config_blob,
        )
        try:
            manifest.save()
        except IntegrityError:
            manifest = models.Manifest.objects.get(digest=manifest.digest)
        ca = ContentArtifact(artifact=artifact, content=manifest, relative_path=manifest.digest)
        try:
            ca.save()
        except IntegrityError:
            pass
        layers = content_data.get("layers")
        blobs = []
        for layer in layers:
            blobs.append(layer.get("digest"))
        blobs_qs = models.Blob.objects.filter(digest__in=blobs)
        thru = []
        for blob in blobs_qs:
            thru.append(models.BlobManifest(manifest=manifest, manifest_blob=blob))
        models.BlobManifest.objects.bulk_create(objs=thru, ignore_conflicts=True, batch_size=1000)
        tag = models.Tag(name=pk, tagged_manifest=manifest)
        try:
            tag.save()
        except IntegrityError:
            tag = models.Tag.objects.get(name=tag.name, tagged_manifest=manifest)

        tags_to_remove = models.Tag.objects.filter(
            pk__in=repository.latest_version().content.all(), name=tag
        ).exclude(tagged_manifest=manifest)
        job = enqueue_with_reservation(
            add_and_remove,
            [repository],
            kwargs={
                "repository_pk": repository.pk,
                "add_content_units": [tag.pk, manifest.pk],
                "remove_content_units": tags_to_remove.values_list("pk"),
            },
        )

        # Wait a small amount of time
        for dummy in range(3):
            time.sleep(1)
            task = Task.objects.get(pk=job.id)
            if task.state == "completed":
                task.delete()
                return ManifestResponse(manifest, path, request, status=201)
            elif task.state in ["waiting", "running"]:
                continue
            else:
                task.delete()
                raise Exception("Failed.")
        raise Throttled(wait=5)

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
            return artifact

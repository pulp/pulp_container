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

from aiohttp.client_exceptions import ClientResponseError, ClientConnectionError
from itertools import chain
from urllib.parse import urljoin, urlparse, urlunparse, parse_qs, urlencode
from tempfile import NamedTemporaryFile

from django.core.files.storage import default_storage as storage
from django.core.files.base import ContentFile, File
from django.db import IntegrityError, transaction
from django.db.models import F, Value
from django.forms.models import model_to_dict
from django.shortcuts import get_object_or_404

from django.conf import settings

from pulpcore.plugin.models import Artifact, ContentArtifact, UploadChunk
from pulpcore.plugin.files import PulpTemporaryUploadedFile
from pulpcore.plugin.tasking import add_and_remove, dispatch
from pulpcore.plugin.util import get_objects_for_user, get_url
from pulpcore.plugin.exceptions import TimeoutException

from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
    ParseError,
    Throttled,
)
from rest_framework.generics import ListAPIView
from rest_framework.pagination import BasePagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import BaseRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.serializers import ModelSerializer
from rest_framework.settings import api_settings
from rest_framework.viewsets import ViewSet
from rest_framework.views import APIView, exception_handler
from rest_framework.status import HTTP_401_UNAUTHORIZED

from pulp_container.app import models, serializers
from pulp_container.app.authorization import AuthorizationService, PermissionChecker
from pulp_container.app.cache import (
    find_base_path_cached,
    FlatpakIndexStaticCache,
    RegistryApiCache,
)
from pulp_container.app.exceptions import (
    BadGateway,
    GatewayTimeout,
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
    filter_resource,
    has_task_completed,
    validate_manifest,
)
from pulp_container.constants import (
    EMPTY_BLOB,
    SIGNATURE_API_EXTENSION_VERSION,
    SIGNATURE_HEADER,
    SIGNATURE_PAYLOAD_MAX_SIZE,
    SIGNATURE_TYPE,
    V2_ACCEPT_HEADERS,
)

log = logging.getLogger(__name__)

IGNORED_PULL_THROUGH_REMOTE_ATTRIBUTES = [
    "remote_ptr",
    "pulp_type",
    "pulp_last_updated",
    "pulp_created",
    "pulp_id",
    "name",
    "includes",
    "excludes",
    "pulp_domain",
]


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
        Adjust the render context for exceptions.
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
        if response.status_code == 500:
            log.error(detail)
        return response

    def get_drv_pull(self, path):
        """
        Get distribution, repository and repository_version for pull access.
        """
        try:
            distribution = models.ContainerDistribution.objects.prefetch_related(
                "pull_through_distribution"
            ).get(base_path=path)
        except models.ContainerDistribution.DoesNotExist:
            # get a pull-through cache distribution whose base_path is a substring of the path
            return self.get_pull_through_drv(path)
        if distribution.repository:
            repository_version = distribution.repository.latest_version()
        elif distribution.repository_version:
            repository_version = distribution.repository_version
        else:
            raise RepositoryNotFound(name=path)
        return distribution, distribution.repository, repository_version

    def get_pull_through_drv(self, path):
        pull_through_cache_distribution = (
            models.ContainerPullThroughDistribution.objects.annotate(path=Value(path))
            .filter(path__startswith=F("base_path"))
            .order_by("-base_path")
            .first()
        )
        if not pull_through_cache_distribution or not self.request.user.is_authenticated:
            raise RepositoryNotFound(name=path)

        upstream_name = path.split(pull_through_cache_distribution.base_path, maxsplit=1)[1].strip(
            "/"
        )
        pull_through_remote = models.ContainerPullThroughRemote.objects.get(
            pk=pull_through_cache_distribution.remote_id
        )
        if not filter_resource(
            upstream_name, pull_through_remote.includes, pull_through_remote.excludes
        ):
            raise RepositoryNotFound(name=path)

        try:
            with transaction.atomic():
                repository, _ = models.ContainerRepository.objects.get_or_create(
                    name=path, retain_repo_versions=1
                )

                remote_data = model_to_dict(
                    pull_through_remote, exclude=IGNORED_PULL_THROUGH_REMOTE_ATTRIBUTES
                )
                remote, _ = models.ContainerRemote.objects.get_or_create(
                    name=path,
                    upstream_name=upstream_name,
                    **remote_data,
                )

                distribution, _ = models.ContainerDistribution.objects.get_or_create(
                    name=path,
                    base_path=path,
                    remote=remote,
                    repository=repository,
                    private=pull_through_cache_distribution.private,
                    namespace=pull_through_cache_distribution.namespace,
                )
        except IntegrityError:
            # some entities needed to be created, but their keys already exist in the database
            # (e.g., a repository with the same name as the constructed path)
            raise RepositoryNotFound(name=path)
        else:
            pull_through_cache_distribution.distributions.add(distribution)

        return distribution, repository, repository.latest_version()

    def get_dr_push(self, request, path, create=False):
        """
        Get distribution and repository for push access.

        Optionally create them if not found.
        """
        try:
            distribution = models.ContainerDistribution.objects.get(base_path=path)
        except models.ContainerDistribution.DoesNotExist:
            if create:
                distribution, repository = self.create_dr(path, request)
            else:
                raise RepositoryNotFound(name=path)
        else:
            repository = distribution.repository
            if repository:
                repository = repository.cast()
                if not repository.PUSH_ENABLED:
                    raise RepositoryInvalid(name=path, message="Repository is read-only.")
            elif create:
                with transaction.atomic():
                    repository = serializers.ContainerPushRepositorySerializer.get_or_create(
                        {"name": path}
                    )
                    distribution.repository = repository
                    distribution.save()
            else:
                raise RepositoryNotFound(name=path)
        return distribution, repository

    def create_dr(self, path, request):
        with transaction.atomic():
            repository = serializers.ContainerPushRepositorySerializer.get_or_create({"name": path})
            distribution = serializers.ContainerDistributionSerializer.get_or_create(
                {"base_path": path, "name": path}, {"repository": get_url(repository)}
            )

            if distribution.repository:
                dist_repository = distribution.repository.cast()
                if not dist_repository.PUSH_ENABLED or repository != dist_repository:
                    raise RepositoryInvalid(name=path, message="Repository is read-only.")
            else:
                distribution.repository = repository
                distribution.save()

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
        scope = request.query_params.getlist("scope", [])

        authorization_service = AuthorizationService(self.request.user, service, scope)
        data = authorization_service.generate_token()
        return Response(data=data)

    def get_exception_handler(self):
        return unauthorized_exception_handler


def unauthorized_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if isinstance(exc, (AuthenticationFailed, NotAuthenticated)):
        response.status_code = HTTP_401_UNAUTHORIZED

    return response


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

    def get_queryset(self, *args, **kwargs):
        """Filter the queryset based on public repositories and assigned permissions."""
        queryset = super().get_queryset()

        distribution_permission = "container.pull_containerdistribution"
        namespace_permission = "container.namespace_pull_containerdistribution"

        if settings.get("TOKEN_AUTH_DISABLED", False):
            return queryset

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


class FlatpakIndexDynamicView(APIView):
    """
    Handles requests to the /index/dynamic endpoint
    """

    authentication_classes = []
    permission_classes = []

    def recurse_through_manifest_lists(self, tag, manifest, oss, architectures, manifests):
        if manifest.media_type in (models.MEDIA_TYPE.MANIFEST_V2, models.MEDIA_TYPE.MANIFEST_OCI):
            manifests.setdefault(manifest, set()).add(tag)
        elif manifest.media_type in (models.MEDIA_TYPE.MANIFEST_LIST, models.MEDIA_TYPE.INDEX_OCI):
            mlms = manifest.listed_manifests.through.objects.filter(image_manifest__pk=manifest.pk)
            if oss:
                mlms.filter(os__in=oss)
            if architectures:
                mlms.filter(architecture__in=architectures)
            for mlm in mlms:
                self.recurse_through_manifest_lists(
                    tag, mlm.manifest_list, oss, architectures, manifests
                )

    def get(self, request):
        req_repositories = None
        req_tags = None
        req_oss = None
        req_architectures = None
        req_label_exists = set()
        req_label_values = {}
        for key, values in request.query_params.lists():
            if key == "repository":
                req_repositories = values
            elif key == "tag":
                req_tags = values
            elif key == "os":
                req_oss = values
            elif key == "architecture":
                req_architectures = values
            elif key.startswith("label:"):
                if key.endswith(":exists"):
                    if any(v != "1" for v in values):
                        raise ParseError(detail=f"{key} must have value 1.")
                    label = key[len("label:") : len(key) - len(":exists")]
                    req_label_exists.add(label)
                else:
                    label = key[len("label:") :]
                    req_label_values[label] = values
            else:
                # In particularly, this covers any annotation:... parameters, which this
                # implementation does not support:
                raise ParseError(detail=f"Unsupported {key}.")

        if "org.flatpak.ref" not in req_label_exists:
            raise ParseError(detail="Missing label:org.flatpak.ref:exists=1.")

        distributions = models.ContainerDistribution.objects.filter(private=False).only("base_path")

        if req_repositories:
            distributions = distributions.filter(base_path__in=req_repositories)

        results = []
        for distribution in distributions:
            images = []
            if distribution.repository:
                repository_version = distribution.repository.latest_version()
            else:
                repository_version = distribution.repository_version
            tags = models.Tag.objects.select_related("tagged_manifest").filter(
                pk__in=repository_version.content
            )
            if req_tags:
                tags = tags.filter(name__in=req_tags)
            manifests = {}  # mapping manifests to sets of encountered tag names
            for tag in tags:
                self.recurse_through_manifest_lists(
                    tag.name, tag.tagged_manifest, req_oss, req_architectures, manifests
                )
            for manifest, tagged in manifests.items():
                with storage.open(manifest.config_blob._artifacts.get().file.name) as file:
                    raw_data = file.read()
                config_data = json.loads(raw_data)
                labels = config_data.get("config", {}).get("Labels")
                if not labels:
                    continue
                if any(label not in labels.keys() for label in req_label_exists):
                    continue
                os = config_data["os"]
                if req_oss and os not in req_oss:
                    continue
                architecture = config_data["architecture"]
                if req_architectures and architecture not in req_architectures:
                    continue
                if any(
                    labels.get(label) not in values for label, values in req_label_values.items()
                ):
                    continue
                images.append(
                    {
                        "Tags": tagged,
                        "Digest": manifest.digest,
                        "MediaType": manifest.media_type,
                        "OS": os,
                        "Architecture": architecture,
                        "Labels": labels,
                    }
                )
            if images:
                results.append({"Name": distribution.base_path, "Images": images})

        return Response(data={"Registry": settings.CONTENT_ORIGIN, "Results": results})


class FlatpakIndexStaticView(FlatpakIndexDynamicView):
    """
    Handles requests to the /index/static endpoint
    """

    @FlatpakIndexStaticCache()
    def get(self, request):
        response = super().get(request)
        # Avoid django.template.response.ContentNotRenderedError:
        response.accepted_renderer = JSONRenderer()
        response.accepted_media_type = JSONRenderer.media_type
        response.renderer_context = {}
        response.render()
        return response


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

        """
        _, repository = self.get_dr_push(request, path, create=True)

        if self.tries_to_mount_blob(request):
            response = self.mount_blob(request, path, repository)
        elif digest := request.query_params.get("digest"):
            # if the digest parameter is present, the request body will be
            # used to complete the upload in a single request.
            # this is monolithic upload
            response = self.single_request_upload(request, path, repository, digest)
        else:
            upload = models.Upload(repository=repository, size=0)
            upload.save()
            response = UploadResponse(upload=upload, path=path, request=request)
        return response

    def create_single_chunk_artifact(self, chunk):
        with transaction.atomic():
            # 1 chunk, create artifact right away
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
        return artifact

    def create_blob(self, artifact, digest):
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
                # re-upload artifact in case it was previously removed.
                ca = ContentArtifact.objects.get(content=blob, relative_path=digest)
                if not ca.artifact:
                    ca.artifact = artifact
                    ca.save(update_fields=["artifact"])
        return blob

    def single_request_upload(self, request, path, repository, digest):
        """Monolithic upload."""
        chunk = request.META["wsgi.input"]
        artifact = self.create_single_chunk_artifact(chunk)
        blob = self.create_blob(artifact, digest)
        repository.pending_blobs.add(blob)
        return BlobResponse(blob, path, 201, request)

    @staticmethod
    def tries_to_mount_blob(request):
        """Check if a client is trying to perform cross repository blob mounting."""
        return request.query_params.keys() == {"from", "mount"}

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

        repository.pending_blobs.add(blob)
        return BlobResponse(blob, path, 201, request)

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
            # podman client claims to do chunked upload, but does not send the range header
            # it sends just one chunk in PATCH and nothing in PUT
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
                artifact = self.create_single_chunk_artifact(chunk)
                upload.artifact = artifact
                if not length:
                    length = artifact.size

            upload.size += length
            upload.save()

        return UploadResponse(upload=upload, path=path, request=request, status=204)

    def put(self, request, path, pk=None):
        """
        Create a blob from uploaded chunks.

        This request makes the upload complete. It can whether carry a zero-length
        body or last chunk can be uploaded.

        """
        _, repository = self.get_dr_push(request, path)

        digest = request.query_params["digest"]
        chunk = request.META["wsgi.input"]
        # last chunk (and the only one) from monolitic upload
        # or last chunk from chunked upload
        last_chunk = ContentFile(chunk.read())
        upload = get_object_or_404(models.Upload, pk=pk, repository=repository)

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
                if last_chunk.size:
                    temp_file.write(last_chunk.read())
                    last_chunk.file.close()
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

        blob = self.create_blob(artifact, digest)
        upload.delete()

        repository.pending_blobs.add(blob)
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
        distribution, repository, repository_version = self.get_drv_pull(path)
        redirects = self.redirects_class(distribution, path, request)

        try:
            blob = models.Blob.objects.get(digest=pk, pk__in=repository_version.content)
        except models.Blob.DoesNotExist:
            if pk == EMPTY_BLOB:
                return redirects.redirect_to_content_app("blobs", pk)
            repository = repository.cast()
            try:
                blob = repository.pending_blobs.get(digest=pk)
                blob.touch()
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
        distribution, repository, repository_version = self.get_drv_pull(path)
        redirects = self.redirects_class(distribution, path, request)

        if pk[:7] != "sha256:":
            try:
                tag = models.Tag.objects.get(name=pk, pk__in=repository_version.content)
            except models.Tag.DoesNotExist:
                distribution = distribution.cast()
                permission_checker = PermissionChecker(request.user)
                if (
                    distribution.remote
                    and distribution.pull_through_distribution
                    and permission_checker.has_pull_through_permissions(distribution)
                ):
                    remote = distribution.remote.cast()
                    # issue a head request first to ensure that the content exists on the remote
                    # source; we want to prevent immediate "not found" error responses from
                    # content-app: 302 (api-app) -> 404 (content-app)
                    manifest = self.fetch_manifest(remote, pk)
                    if manifest is None:
                        return redirects.redirect_to_content_app("manifests", pk)

                    tag = models.Tag(name=pk, tagged_manifest=manifest)
                    try:
                        tag.save()
                    except IntegrityError:
                        tag = models.Tag.objects.get(name=tag.name, tagged_manifest=manifest)
                        tag.touch()

                    add_content_units = self.get_content_units_to_add(manifest, tag)

                    dispatch(
                        add_and_remove,
                        exclusive_resources=[repository],
                        kwargs={
                            "repository_pk": str(repository.pk),
                            "add_content_units": add_content_units,
                            "remove_content_units": [],
                        },
                        immediate=True,
                        deferred=True,
                    )

                    return redirects.redirect_to_content_app("manifests", tag.name)
                else:
                    raise ManifestNotFound(reference=pk)

            return redirects.issue_tag_redirect(tag)
        else:
            try:
                manifest = models.Manifest.objects.get(digest=pk, pk__in=repository_version.content)
                return redirects.issue_manifest_redirect(manifest)
            except models.Manifest.DoesNotExist:
                repository = repository.cast()
                # the manifest might be a part of listed manifests currently being uploaded
                # or saved during the pull-through caching
                try:
                    manifest = repository.pending_manifests.get(digest=pk)
                    manifest.touch()
                except models.Manifest.DoesNotExist:
                    manifest = None

                distribution = distribution.cast()
                permission_checker = PermissionChecker(request.user)
                if (
                    distribution.remote
                    and distribution.pull_through_distribution
                    and permission_checker.has_pull_through_permissions(distribution)
                ):
                    remote = distribution.remote.cast()
                    self.fetch_manifest(remote, pk)
                    return redirects.redirect_to_content_app("manifests", pk)
                elif manifest:
                    return redirects.issue_manifest_redirect(manifest)
                else:
                    raise ManifestNotFound(reference=pk)

    def get_content_units_to_add(self, manifest, tag):
        add_content_units = [str(tag.pk), str(manifest.pk)]
        if manifest.media_type in (
            models.MEDIA_TYPE.MANIFEST_LIST,
            models.MEDIA_TYPE.INDEX_OCI,
        ):
            for listed_manifest in manifest.listed_manifests.all():
                add_content_units.append(listed_manifest.pk)
                add_content_units.append(listed_manifest.config_blob_id)
                add_content_units.extend(listed_manifest.blobs.values_list("pk", flat=True))
        elif manifest.media_type in (
            models.MEDIA_TYPE.MANIFEST_V2,
            models.MEDIA_TYPE.MANIFEST_OCI,
        ):
            add_content_units.append(manifest.config_blob_id)
            add_content_units.extend(manifest.blobs.values_list("pk", flat=True))
        else:
            add_content_units.extend(manifest.blobs.values_list("pk", flat=True))
        return add_content_units

    def fetch_manifest(self, remote, pk):
        relative_url = "/v2/{name}/manifests/{pk}".format(
            name=remote.namespaced_upstream_name, pk=pk
        )
        tag_url = urljoin(remote.url, relative_url)
        downloader = remote.get_downloader(url=tag_url)
        try:
            response = downloader.fetch(
                extra_data={"headers": V2_ACCEPT_HEADERS, "http_method": "head"}
            )
        except ClientResponseError as response_error:
            if response_error.status == 429:
                # the client could request the manifest outside the docker hub pull limit;
                # it is necessary to pass this information back to the client
                raise Throttled()
            elif response_error.status == 404:
                raise ManifestNotFound(reference=pk)
            else:
                raise BadGateway(detail=response_error.message)
        except (ClientConnectionError, TimeoutException):
            # The remote server is not available at the moment
            raise GatewayTimeout()
        else:
            digest = response.headers.get("docker-content-digest")
            return models.Manifest.objects.filter(digest=digest).first()

    def put(self, request, path, pk=None):
        """
        Responds with the actual manifest
        """
        # iterate over all the layers and create
        chunk = request.META["wsgi.input"]
        artifact = self.receive_artifact(chunk)
        manifest_digest = "sha256:{id}".format(id=artifact.sha256)

        with storage.open(artifact.file.name, mode="rb") as artifact_file:
            raw_bytes_data = artifact_file.read()

        raw_text_data = raw_bytes_data.decode("utf-8")
        content_data = json.loads(raw_text_data)

        media_type = determine_media_type(content_data, request)
        validate_manifest(content_data, media_type, manifest_digest)

        # when a user uploads a manifest list with zero listed manifests (no blobs were uploaded
        # before) and the specified repository has not been created yet, create the repository
        # without raising an error
        is_manifest_list = media_type in (
            models.MEDIA_TYPE.MANIFEST_LIST,
            models.MEDIA_TYPE.INDEX_OCI,
        )
        _, repository = self.get_dr_push(request, path, create=is_manifest_list)

        latest_version_content_pks = repository.latest_version().content.values_list("pk")
        manifests_pks = repository.pending_manifests.values_list("pk")
        blobs_pks = repository.pending_blobs.values_list("pk")
        content_pks = latest_version_content_pks.union(manifests_pks).union(blobs_pks)

        found_manifests = models.Manifest.objects.none()

        if is_manifest_list:
            manifests = {}
            for manifest in content_data.get("manifests"):
                manifests[manifest["digest"]] = manifest["platform"]

            digests = set(manifests.keys())

            found_manifests = models.Manifest.objects.filter(digest__in=digests, pk__in=content_pks)

            if (len(manifests) - found_manifests.count()) != 0:
                ManifestInvalid(digest=manifest_digest)

            manifest_list = self._init_manifest(manifest_digest, media_type, raw_text_data)
            manifest_list = self._save_manifest(manifest_list)

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

            # once relations for listed manifests are established, it is
            # possible to initialize the nature of the manifest list
            if manifest.init_manifest_list_nature():
                manifest.save(update_fields=["is_bootable", "is_flatpak"])

            found_blobs = models.Blob.objects.filter(
                digest__in=found_manifests.values_list("blobs__digest"),
                pk__in=content_pks,
            )
            found_config_blobs = models.Blob.objects.filter(
                digest__in=found_manifests.values_list("config_blob__digest"),
                pk__in=content_pks,
            )
        else:
            # both docker/oci format should contain config, digest, mediaType, size
            config_layer = content_data.get("config")
            if not config_layer:
                raise ManifestInvalid(
                    digest=manifest_digest,
                    reason="Pushing manifests of the version V1 is not supported",
                )

            config_digest = config_layer.get("digest")
            found_config_blobs = models.Blob.objects.filter(
                digest=config_digest, pk__in=content_pks
            )
            if not found_config_blobs.exists():
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

            found_blobs = models.Blob.objects.filter(digest__in=blobs, pk__in=content_pks)
            if (len(blobs) - found_blobs.count()) != 0:
                raise ManifestInvalid(digest=manifest_digest)

            config_blob = found_config_blobs.first()
            manifest = self._init_manifest(manifest_digest, media_type, raw_text_data, config_blob)
            manifest.init_metadata(manifest_data=content_data)

            manifest = self._save_manifest(manifest)

            thru = []
            for blob in found_blobs:
                thru.append(models.BlobManifest(manifest=manifest, manifest_blob=blob))
            models.BlobManifest.objects.bulk_create(
                objs=thru, ignore_conflicts=True, batch_size=1000
            )

        # a manifest cannot be tagged by its digest - an identifier specified in the 'pk' parameter
        if not pk.startswith("sha256:"):
            tag = models.Tag(name=pk, tagged_manifest=manifest)
            try:
                tag.save()
            except IntegrityError:
                tag = models.Tag.objects.get(name=tag.name, tagged_manifest=manifest)
                tag.touch()

            add_content_units = [str(tag.pk), str(manifest.pk)] + [
                str(content.pk)
                for content in chain(found_blobs, found_config_blobs, found_manifests)
            ]

            tags_to_remove = models.Tag.objects.filter(
                pk__in=repository.latest_version().content.all(), name=tag
            ).exclude(tagged_manifest=manifest)
            remove_content_units = [str(pk) for pk in tags_to_remove.values_list("pk")]

            immediate_task = dispatch(
                add_and_remove,
                exclusive_resources=[repository],
                kwargs={
                    "repository_pk": str(repository.pk),
                    "add_content_units": add_content_units,
                    "remove_content_units": remove_content_units,
                },
                immediate=True,
                deferred=True,
            )

            if immediate_task.state == "completed":
                return ManifestResponse(manifest, path, request, status=201)
            elif immediate_task.state == "canceled":
                raise Throttled()
            elif immediate_task.state in ["waiting", "running"]:
                if has_task_completed(immediate_task, wait_in_seconds=2):
                    return ManifestResponse(manifest, path, request, status=201)
            else:
                raise Exception(str(immediate_task.error))
        else:
            # the client pushed a listed manifest
            repository.pending_manifests.add(manifest)
            return ManifestResponse(manifest, path, request, status=201)

    def _init_manifest(self, manifest_digest, media_type, raw_text_data, config_blob=None):
        return models.Manifest(
            digest=manifest_digest,
            schema_version=2,
            media_type=media_type,
            config_blob=config_blob,
            data=raw_text_data,
        )

    def _save_manifest(self, manifest):
        try:
            manifest.save()
        except IntegrityError:
            manifest = models.Manifest.objects.get(digest=manifest.digest)
            manifest.touch()

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
            try:
                # the manifest was initialized as a pending content unit
                # or has not been assigned to any repository yet
                manifest = models.Manifest.objects.get(digest=pk)
                manifest.touch()
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

        immediate_task = dispatch(
            add_and_remove,
            exclusive_resources=[repository],
            kwargs={
                "repository_pk": str(repository.pk),
                "add_content_units": [str(signature.pk)],
                "remove_content_units": [],
            },
            immediate=True,
            deferred=True,
        )

        if immediate_task.state == "completed":
            return ManifestSignatureResponse(signature, path)
        elif immediate_task.state == "canceled":
            raise Throttled()
        elif immediate_task.state in ["waiting", "running"]:
            if has_task_completed(immediate_task, wait_in_seconds=2):
                return ManifestSignatureResponse(signature, path)
        else:
            raise Exception(str(immediate_task.error))

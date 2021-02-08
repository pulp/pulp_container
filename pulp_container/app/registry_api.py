"""
Check `Plugin Writer's Guide`_ for more details.

. _Plugin Writer's Guide:
    http://docs.pulpproject.org/plugins/plugin-writer/index.html
"""
import json
import logging
import hashlib
import re
from tempfile import NamedTemporaryFile

from django.core.files.storage import default_storage as storage
from django.core.files.base import ContentFile, File
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404

from django.conf import settings

from pulpcore.plugin.models import Artifact, ContentArtifact, UploadChunk
from pulpcore.plugin.files import PulpTemporaryUploadedFile
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
    NotFound,
    ParseError,
    ValidationError,
)
from rest_framework.renderers import BaseRenderer, JSONRenderer
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet
from rest_framework.views import APIView

from pulp_container.app import models, serializers
from pulp_container.app.authorization import AuthorizationService
from pulp_container.app.redirects import FileStorageRedirects, S3StorageRedirects
from pulp_container.app.token_verification import TokenAuthentication, TokenPermission


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
            "Range": f"0-{upload.size}",
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

        log.info("digest: {digest}".format(digest=blob.digest))
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

    authentication_classes = [TokenAuthentication]
    permission_classes = [TokenPermission]
    schema = None

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
        return super().handle_exception(exc)

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
                    repo_serializer = serializers.ContainerPushRepositorySerializer(
                        data={"name": path}, context={"request": request}
                    )
                    repo_serializer.is_valid(raise_exception=True)
                    repository = repo_serializer.create(repo_serializer.validated_data)
                    distribution.repository = repository
                    distribution.save()
            else:
                raise RepositoryNotFound(name=path)
        return distribution, repository


class BearerTokenView(APIView):
    """
    Hand out anonymous or authenticated bearer tokens.
    """

    # Allow everyone to access but still value authenticated users.
    permission_classes = []

    EMPTY_ACCESS_SCOPE = "::"

    def get(self, request):
        """Handles GET requests for the /token/ endpoint."""
        try:
            service = request.query_params["service"]
        except KeyError:
            raise ParseError(detail="No service name provided.")
        scope = request.query_params.get("scope", self.EMPTY_ACCESS_SCOPE)

        authorization_service = AuthorizationService(self.request.user, service, scope)
        data = authorization_service.generate_token()
        return Response(data=data)


class VersionView(ContainerRegistryApiMixin, APIView):
    """
    Handles requests to the /v2/ endpoint.
    """

    def get(self, request):
        """Handles GET requests for the /v2/ endpoint."""
        return Response(data={})


class CatalogView(ContainerRegistryApiMixin, APIView):
    """
    Handles requests to the /v2/_catalog endpoint
    """

    def get(self, request):
        """Handles GET requests for the /v2/_catalog endpoint."""
        repositories_names = models.ContainerDistribution.objects.values_list(
            "base_path", flat=True
        )
        return Response(data={"repositories": list(repositories_names)})


class TagsListView(ContainerRegistryApiMixin, APIView):
    """
    Handles requests to the /v2/<repo>/tags/list endpoint
    """

    def get(self, request, path):
        """
        Handles GET requests to the /v2/<repo>/tags/list endpoint
        """
        _, _, repository_version = self.get_drv_pull(path)
        tags = {"name": path, "tags": set()}
        for c in repository_version.content:
            c = c.cast()
            if isinstance(c, models.Tag):
                tags["tags"].add(c.name)
        tags["tags"] = list(tags["tags"])
        return Response(data=tags)


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
        upload = models.Upload.objects.get(pk=pk, repository=repository)
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

            with repository.new_version() as new_version:
                new_version.add_content(models.Blob.objects.filter(pk=blob.pk))

            upload.delete()

            return BlobResponse(blob, path, 201, request)
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
            pass
        with repository.new_version() as new_version:
            new_version.add_content(models.Manifest.objects.filter(digest=manifest.digest))
            new_version.remove_content(models.Tag.objects.filter(name=tag.name))
            new_version.add_content(
                models.Tag.objects.filter(name=tag.name, tagged_manifest=manifest)
            )
        return ManifestResponse(manifest, path, request, status=201)

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

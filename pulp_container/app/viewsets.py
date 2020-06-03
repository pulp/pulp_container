"""
Check `Plugin Writer's Guide`_ for more details.

. _Plugin Writer's Guide:
    http://docs.pulpproject.org/en/3.0/nightly/plugins/plugin-writer/index.html
"""
import json
import logging
import hashlib
import re
from tempfile import NamedTemporaryFile

from django.core.files.storage import default_storage as storage

from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.http import Http404
from django_filters import MultipleChoiceFilter
from drf_yasg.utils import swagger_auto_schema

from django.conf import settings
from django.core.files.base import ContentFile
from django.http import HttpResponseRedirect

from pulpcore.plugin.serializers import (
    AsyncOperationResponseSerializer,
    RepositorySyncURLSerializer,
)
from pulpcore.plugin.models import (
    Artifact,
    Content,
    ContentArtifact
)
from pulpcore.plugin.tasking import enqueue_with_reservation
from pulpcore.plugin.viewsets import (
    BaseDistributionViewSet,
    CharInFilter,
    ContentFilter,
    NamedModelViewSet,
    ReadOnlyContentViewSet,
    RemoteViewSet,
    RepositoryViewSet,
    RepositoryVersionViewSet,
    OperationPostponedResponse,
)
from rest_framework.decorators import action
from rest_framework.renderers import BaseRenderer
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet
from rest_framework.views import APIView

from . import models, serializers, tasks


log = logging.getLogger(__name__)


class TagFilter(ContentFilter):
    """
    FilterSet for Tags.
    """

    media_type = MultipleChoiceFilter(
        choices=models.Manifest.MANIFEST_CHOICES,
        field_name='tagged_manifest__media_type',
        lookup_expr='contains',
    )
    digest = CharInFilter(field_name='tagged_manifest__digest', lookup_expr='in')

    class Meta:
        model = models.Tag
        fields = {
            'name': ['exact', 'in'],
        }


class ManifestFilter(ContentFilter):
    """
    FilterSet for Manifests.
    """

    media_type = MultipleChoiceFilter(choices=models.Manifest.MANIFEST_CHOICES)

    class Meta:
        model = models.Manifest
        fields = {
            'digest': ['exact', 'in'],
        }


class TagViewSet(ReadOnlyContentViewSet):
    """
    ViewSet for Tag.
    """

    endpoint_name = 'tags'
    queryset = models.Tag.objects.all()
    serializer_class = serializers.TagSerializer
    filterset_class = TagFilter


class ManifestViewSet(ReadOnlyContentViewSet):
    """
    ViewSet for Manifest.
    """

    endpoint_name = 'manifests'
    queryset = models.Manifest.objects.all()
    serializer_class = serializers.ManifestSerializer
    filterset_class = ManifestFilter


class BlobFilter(ContentFilter):
    """
    FilterSet for Blobs.
    """

    media_type = MultipleChoiceFilter(choices=models.Blob.BLOB_CHOICES)

    class Meta:
        model = models.Blob
        fields = {
            'digest': ['exact', 'in'],
        }


class BlobViewSet(ReadOnlyContentViewSet):
    """
    ViewSet for Blobs.
    """

    endpoint_name = 'blobs'
    queryset = models.Blob.objects.all()
    serializer_class = serializers.BlobSerializer
    filterset_class = BlobFilter


class ContainerRemoteViewSet(RemoteViewSet):
    """
    Container remotes represent an external repository that implements the Container
    Registry API. Container remotes support deferred downloading by configuring
    the ``policy`` field.  ``on_demand`` and ``streamed`` policies can provide
    significant disk space savings.
    """

    endpoint_name = 'container'
    queryset = models.ContainerRemote.objects.all()
    serializer_class = serializers.ContainerRemoteSerializer


class ContainerRepositoryViewSet(RepositoryViewSet):
    """
    ViewSet for container repo.
    """

    endpoint_name = 'container'
    queryset = models.ContainerRepository.objects.all()
    serializer_class = serializers.ContainerRepositorySerializer

    # This decorator is necessary since a sync operation is asyncrounous and returns
    # the id and href of the sync task.
    @swagger_auto_schema(
        operation_description="Trigger an asynchronous task to sync content.",
        operation_summary="Sync from a remote",
        responses={202: AsyncOperationResponseSerializer}
    )
    @action(detail=True, methods=['post'], serializer_class=RepositorySyncURLSerializer)
    def sync(self, request, pk):
        """
        Synchronizes a repository. The ``repository`` field has to be provided.
        """
        repository = self.get_object()
        serializer = RepositorySyncURLSerializer(
            data=request.data,
            context={'request': request}
        )

        # Validate synchronously to return 400 errors.
        serializer.is_valid(raise_exception=True)
        remote = serializer.validated_data.get('remote')
        mirror = serializer.validated_data.get('mirror')

        result = enqueue_with_reservation(
            tasks.synchronize,
            [repository, remote],
            kwargs={
                'remote_pk': remote.pk,
                'repository_pk': repository.pk,
                'mirror': mirror
            }
        )
        return OperationPostponedResponse(result, request)

    @swagger_auto_schema(
        operation_description="Trigger an asynchronous task to tag an image in the repository",
        operation_summary="Create a Tag",
        responses={202: AsyncOperationResponseSerializer},
        request_body=serializers.TagImageSerializer,
    )
    @action(detail=True, methods=['post'], serializer_class=serializers.TagImageSerializer)
    def tag(self, request, pk):
        """
        Create a task which is responsible for creating a new tag.
        """
        repository = self.get_object()
        request.data['repository'] = repository

        serializer = serializers.TagImageSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        manifest = serializer.validated_data['manifest']
        tag = serializer.validated_data['tag']

        result = enqueue_with_reservation(
            tasks.tag_image,
            [repository, manifest],
            kwargs={
                'manifest_pk': manifest.pk,
                'tag': tag,
                'repository_pk': repository.pk
            }
        )
        return OperationPostponedResponse(result, request)

    @swagger_auto_schema(
        operation_description="Trigger an asynchronous task to untag an image in the repository",
        operation_summary="Delete a tag",
        responses={202: AsyncOperationResponseSerializer},
        request_body=serializers.UnTagImageSerializer,
    )
    @action(detail=True, methods=['post'], serializer_class=serializers.UnTagImageSerializer)
    def untag(self, request, pk):
        """
        Create a task which is responsible for untagging an image.
        """
        repository = self.get_object()
        request.data['repository'] = repository

        serializer = serializers.UnTagImageSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        tag = serializer.validated_data['tag']

        result = enqueue_with_reservation(
            tasks.untag_image,
            [repository],
            kwargs={
                'tag': tag,
                'repository_pk': repository.pk
            }
        )
        return OperationPostponedResponse(result, request)

    @swagger_auto_schema(
        operation_description="Trigger an asynchronous task to recursively add container content.",
        operation_summary="Add content",
        responses={202: AsyncOperationResponseSerializer},
        request_body=serializers.RecursiveManageSerializer,
    )
    @action(detail=True, methods=['post'], serializer_class=serializers.RecursiveManageSerializer)
    def add(self, request, pk):
        """
        Queues a task that creates a new RepositoryVersion by adding content units.
        """
        add_content_units = []
        repository = self.get_object()
        serializer = serializers.RecursiveManageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if 'content_units' in request.data:
            for url in request.data['content_units']:
                content = NamedModelViewSet.get_resource(url, Content)
                add_content_units.append(content.pk)

        result = enqueue_with_reservation(
            tasks.recursive_add_content, [repository],
            kwargs={
                'repository_pk': repository.pk,
                'content_units': add_content_units,
            }
        )
        return OperationPostponedResponse(result, request)

    @swagger_auto_schema(
        operation_description="Trigger an async task to recursively remove container content.",
        operation_summary="Remove content",
        responses={202: AsyncOperationResponseSerializer},
        request_body=serializers.RecursiveManageSerializer,
    )
    @action(detail=True, methods=['post'], serializer_class=serializers.RecursiveManageSerializer)
    def remove(self, request, pk):
        """
        Queues a task that creates a new RepositoryVersion by removing content units.
        """
        remove_content_units = []
        repository = self.get_object()
        serializer = serializers.RecursiveManageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if 'content_units' in request.data:
            for url in request.data['content_units']:
                if url == '*':
                    remove_content_units = [url]
                    break

                content = NamedModelViewSet.get_resource(url, Content)
                remove_content_units.append(content.pk)

        result = enqueue_with_reservation(
            tasks.recursive_remove_content, [repository],
            kwargs={
                'repository_pk': repository.pk,
                'content_units': remove_content_units,
            }
        )
        return OperationPostponedResponse(result, request)

    @swagger_auto_schema(
        operation_description="Trigger an asynchronous task to copy tags",
        operation_summary="Copy tags",
        responses={202: AsyncOperationResponseSerializer},
        request_body=serializers.TagCopySerializer,
    )
    @action(detail=True, methods=['post'], serializer_class=serializers.TagCopySerializer)
    def copy_tags(self, request, pk):
        """
        Queues a task that creates a new RepositoryVersion by adding Tags.
        """
        names = request.data.get("names")
        serializer = serializers.TagCopySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        repository = self.get_object()
        source_latest = serializer.validated_data['source_repository_version']
        content_tags_in_repo = source_latest.content.filter(
            pulp_type="container.tag"
        )
        tags_in_repo = models.Tag.objects.filter(
            pk__in=content_tags_in_repo,
        )
        if names is None:
            tags_to_add = tags_in_repo
        else:
            tags_to_add = tags_in_repo.filter(name__in=names)

        result = enqueue_with_reservation(
            tasks.recursive_add_content, [repository],
            kwargs={
                'repository_pk': repository.pk,
                'content_units': tags_to_add.values_list('pk', flat=True),
            }
        )
        return OperationPostponedResponse(result, request)

    @swagger_auto_schema(
        operation_description="Trigger an asynchronous task to copy manifests",
        operation_summary="Copy manifests",
        responses={202: AsyncOperationResponseSerializer},
        request_body=serializers.ManifestCopySerializer,
    )
    @action(detail=True, methods=['post'], serializer_class=serializers.ManifestCopySerializer)
    def copy_manifests(self, request, pk):
        """
        Queues a task that creates a new RepositoryVersion by adding Manifests.
        """
        serializer = serializers.ManifestCopySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        repository = self.get_object()
        source_latest = serializer.validated_data['source_repository_version']
        content_manifests_in_repo = source_latest.content.filter(
            pulp_type="container.manifest"
        )
        manifests_in_repo = models.Manifest.objects.filter(
            pk__in=content_manifests_in_repo,
        )
        digests = request.data.get("digests")
        media_types = request.data.get("media_types")
        filters = {}
        if digests is not None:
            filters['digest__in'] = digests
        if media_types is not None:
            filters['media_type__in'] = media_types
        manifests_to_add = manifests_in_repo.filter(**filters)
        result = enqueue_with_reservation(
            tasks.recursive_add_content, [repository],
            kwargs={
                'repository_pk': repository.pk,
                'content_units': manifests_to_add,
            }
        )
        return OperationPostponedResponse(result, request)

    @swagger_auto_schema(
        operation_description="Trigger an asynchronous task to build an OCI image from a "
                              "Containerfile. A new repository version is created with the new "
                              "image and tag. This API is tech preview in Pulp Container 1.1. "
                              "Backwards compatibility when upgrading is not guaranteed.",
        operation_summary="Build an Image",
        responses={202: AsyncOperationResponseSerializer},
        request_body=serializers.OCIBuildImageSerializer,
    )
    @action(detail=True, methods=['post'], serializer_class=serializers.TagImageSerializer)
    def build_image(self, request, pk):
        """
        Create a task which is responsible for creating a new image and tag.
        """
        repository = self.get_object()

        serializer = serializers.OCIBuildImageSerializer(
            data=request.data,
            context={'request': request}
        )

        serializer.is_valid(raise_exception=True)

        containerfile = serializer.validated_data['containerfile_artifact']
        try:
            containerfile.save()
        except IntegrityError:
            containerfile = Artifact.objects.get(sha256=containerfile.sha256)
        tag = serializer.validated_data['tag']

        artifacts = serializer.validated_data['artifacts']

        result = enqueue_with_reservation(
            tasks.build_image_from_containerfile,
            [repository],
            kwargs={
                'containerfile_pk': containerfile.pk,
                'tag': tag,
                'repository_pk': repository.pk,
                'artifacts': artifacts
            }
        )
        return OperationPostponedResponse(result, request)


class ContainerRepositoryVersionViewSet(RepositoryVersionViewSet):
    """
    ContainerRepositoryVersion represents a single container repository version.
    """

    parent_viewset = ContainerRepositoryViewSet


class ContainerDistributionViewSet(BaseDistributionViewSet):
    """
    The Container Distribution will serve the latest version of a Repository if
    ``repository`` is specified. The Container Distribution will serve a specific
    repository version if ``repository_version``. Note that **either**
    ``repository`` or ``repository_version`` can be set on a Container
    Distribution, but not both.
    """

    endpoint_name = 'container'
    queryset = models.ContainerDistribution.objects.all()
    serializer_class = serializers.ContainerDistributionSerializer


class ManifestRenderer(BaseRenderer):
    """
    Rendered class for rendering Manifest responses.
    """

    media_type = "*/*"
    format = 'txt'

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
        headers = {'Docker-Distribution-Api-Version': 'registry/2.0',
                   'Docker-Upload-UUID': upload.pk,
                   'Location': '/v2/{path}/blobs/uploads/{pk}'.format(path=path, pk=upload.pk),
                   'Range': '0-{offset}'.format(offset=upload.file.size),
                   'Content-Length': content_length
                   }
        super().__init__(headers=headers, status=202)


class ManifestResponse(Response):
    """
    An HTTP response class for returning Manifets.
    """

    def __init__(self, manifest, path, request, status=200, send_body=False):
        """
        Args:
            manifest (pulp_container.app.models.Manifest): A Manifest model used to generate the
                response.
            path (str): The base_path of the ContainerDistribution (Container repository name)
            request (rest_framework.request.Request): Request object not used by this
                implementation of Response.
            status (int): Status code to send with the response.
            send_body (bool): Whether a body should be sent with the response or just the headers.
        """
        artifact = manifest._artifacts.get()
        if send_body:
            size = artifact.size
        else:
            size = 0
        headers = {'Docker-Distribution-Api-Version': 'registry/2.0',
                   'Docker-Content-Digest': manifest.digest,
                   'Location': '/v2/{path}/manifests/{digest}'.format(path=path,
                                                                      digest=manifest.digest),
                   'Content-Length': size
                   }
        super().__init__(headers=headers, status=status)


class BlobResponse(Response):
    """
    An HTTP response class for returning Blobs.
    """

    def __init__(self, blob, path, status, request, send_body=False):
        """
        Args:
            blob (pulp_container.app.models.Blob): A Blob model used to generate the response.
            path (str): The base_path of the ContainerDistribution (Container repository name)
            request (rest_framework.request.Request): Request object not used by this
                implementation of Response.
            status (int): Status code to send with the response.
            send_body (bool): Whether a body should be sent with the response or just the
                headers.
        """
        artifact = blob._artifacts.get()
        size = artifact.size

        log.info('digest: {digest}'.format(digest=blob.digest))
        headers = {'Docker-Distribution-Api-Version': 'registry/2.0',
                   'Docker-Content-Digest': blob.digest,
                   'Location': '/v2/{path}/blobs/{digest}'.format(path=path, digest=blob.digest),
                   'Etag': blob.digest,
                   'Range': '0-{offset}'.format(offset=int(size)),
                   'Content-Length': size,
                   'Content-Type': 'application/octet-stream',
                   'Connection': 'close'
                   }
        super().__init__(headers=headers, status=status)


class VersionView(APIView):
    """
    Handles requests to the /v2/ endpoint.
    """

    # allow anyone to access
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """Handles GET requests for the /v2/ endpoint."""
        headers = {'Docker-Distribution-Api-Version': 'registry/2.0',
                   }
        return Response(data={}, headers=headers)


class CatalogView(APIView):
    """
    Handles requests to the /v2/_catalog endpoint
    """

    # allow anyone to access
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        """Handles GET requests for the /v2/_catalog endpoint."""
        repositories_names = models.ContainerDistribution.objects.values_list('base_path',
                                                                              flat=True)
        headers = {'Docker-Distribution-API-Version': 'registry/2.0'}
        return Response(data={'repositories': list(repositories_names)}, headers=headers)


class TagsListView(APIView):
    """
    Handles requests to the /v2/<repo>/tags/list endpoint
    """

    # allow anyone to access
    authentication_classes = []
    permission_classes = []

    def get(self, request, path):
        """
        Handles GET requests to the /v2/<repo>/tags/list endpoint
        """
        distribution = get_object_or_404(models.ContainerDistribution, base_path=path)
        if distribution.repository:
            repository = distribution.repository
            repository_version = repository.latest_version()
        elif distribution.repository_version:
            repository_version = distribution.repository_version
        else:
            raise Http404("Repository {} does not exist.".format(path))
        tags = {'name': path, 'tags': set()}
        for c in repository_version.content:
            c = c.cast()
            if isinstance(c, models.Tag):
                tags['tags'].add(c.name)
        tags['tags'] = list(tags['tags'])
        headers = {'Docker-Distribution-API-Version': 'registry/2.0'}
        return Response(data=tags, headers=headers)


class BlobUploads(ViewSet):
    """
    The ViewSet for handling uploading of blobs.
    """

    model = models.Upload
    queryset = models.Upload.objects.all()

    # allow anyone to access
    authentication_classes = []
    permission_classes = []

    content_range_pattern = re.compile(r'^(?P<start>\d+)-(?P<end>\d+)$')

    def create(self, request, path):
        """
        This methods handles the creation of an upload.
        """
        # TODO add repo push type to distinguish from sync repo type
        distribution, _ = models.ContainerDistribution.objects.get_or_create(
            name=path, base_path=path)
        repository = distribution.repository
        if not repository:
            repository, _ = models.ContainerRepository.objects.get_or_create(name=path)
            distribution.repository = repository
            distribution.save()

        upload = models.Upload(repository=repository)
        upload.file.save(name='', content=ContentFile(''), save=False)
        upload.save()
        response = UploadResponse(upload=upload, path=path, content_length=0, request=request)

        return response

    def partial_update(self, request, path, pk=None):
        """
        This methods handles uploading of a chunk to an existing upload.
        """
        distribution = get_object_or_404(models.ContainerDistribution, base_path=path)
        if distribution.repository:
            repository = distribution.repository
        else:
            raise Http404("Repository {} does not exist.".format(path))
        chunk = request.META['wsgi.input']
        if 'Content-Range' in request.headers or 'digest' not in request.query_params:
            whole = False
        else:
            whole = True

        if whole:
            start = 0
            end = chunk.size - 1
        else:
            content_range = request.META.get('HTTP_CONTENT_RANGE', '')
            match = self.content_range_pattern.match(content_range)
            if not match:
                start = 0
                end = 0
                chunk_size = 0
            else:
                start = int(match.group('start'))
                end = int(match.group('end'))
                chunk_size = end - start + 1

        upload = get_object_or_404(models.Upload, repository=repository, pk=pk)

        if upload.offset != start:
            raise Exception
        upload.append_chunk(chunk, chunk_size=chunk_size)
        upload.save()
        return UploadResponse(upload=upload, path=path, content_length=upload.file.size,
                              request=request)

    def put(self, request, path, pk=None):
        """Handles creation of Uploads."""
        distribution = get_object_or_404(models.ContainerDistribution, base_path=path)
        if distribution.repository:
            repository = distribution.repository
        else:
            raise Http404("Repository {} does not exist.".format(path))

        digest = request.query_params['digest']
        upload = models.Upload.objects.get(pk=pk, repository=repository)

        if upload.sha256 == digest[len("sha256:"):]:
            try:
                artifact = Artifact(file=upload.file.name, md5=upload.md5, sha1=upload.sha1,
                                    sha256=upload.sha256, sha384=upload.sha384,
                                    sha512=upload.sha512, size=upload.file.size)
                artifact.save()
            except IntegrityError:
                artifact = Artifact.objects.get(sha256=artifact.sha256)
            try:
                blob = models.Blob(digest=digest, media_type=models.MEDIA_TYPE.REGULAR_BLOB)
                blob.save()
            except IntegrityError:
                blob = models.Blob.objects.get(digest=digest)
            try:
                blob_artifact = ContentArtifact(artifact=artifact, content=blob,
                                                relative_path=digest)
                blob_artifact.save()
            except IntegrityError:
                pass

            with repository.new_version() as new_version:
                new_version.add_content(models.Blob.objects.filter(pk=blob.pk))

            upload.delete()

            return BlobResponse(blob, path, 201, request)
        else:
            raise Exception("The digest did not match")


class Blobs(ViewSet):
    """
    ViewSet for interacting with Blobs
    """

    # allow anyone to access
    authentication_classes = []
    permission_classes = []

    def head(self, request, path, pk=None):
        """
        Responds to HEAD requests about blobs
        :param request:
        :param path:
        :param digest:
        :return:
        """
        distribution = get_object_or_404(models.ContainerDistribution, base_path=path)
        if distribution.repository:
            repository = distribution.repository
            repository_version = repository.latest_version()
        elif distribution.repository_version:
            repository_version = distribution.repository_version
        else:
            raise Http404("Repository {} does not exist.".format(path))
        if not repository_version:
            raise Http404("Blob does not exist: {digest}".format(digest=pk))
        blob = get_object_or_404(models.Blob, digest=pk, pk__in=repository_version.content)
        return BlobResponse(blob, path, 200, request)

    def get(self, request, path, pk=None):
        """Handles GET requests for Blobs."""
        distribution = get_object_or_404(models.ContainerDistribution, base_path=path)
        if distribution.repository:
            repository = distribution.repository
            repository_version = repository.latest_version()
        elif distribution.repository_version:
            repository_version = distribution.repository_version
        else:
            raise Http404("Repository {} does not exist.".format(path))
        blob = get_object_or_404(models.Blob, digest=pk, pk__in=repository_version.content)
        return HttpResponseRedirect("{}/pulp/container/{}/blobs/{}".format(settings.CONTENT_ORIGIN,
                                                                           path, blob.digest))


class Manifests(ViewSet):
    """
    ViewSet for intereacting with Manifests
    """

    # allow anyone to access
    authentication_classes = []
    permission_classes = []
    renderer_classes = [ManifestRenderer]
    # The lookup regex does not allow /, ^, &, *, %, !, ~, @, #, +, =, ?
    lookup_value_regex = '[^/^&*%!~@#+=?]+'

    def head(self, request, path, pk=None):
        """
        Responds to HEAD requests about manifests by reference
        :param request:
        :param path:
        :param digest:
        :return:
        """
        distribution = get_object_or_404(models.ContainerDistribution, base_path=path)
        if distribution.repository:
            repository = distribution.repository
            repository_version = repository.latest_version()
        elif distribution.repository_version:
            repository_version = distribution.repository_version
        else:
            raise Http404("Repository {} does not exist.".format(path))
        if pk[:7] != 'sha256:':
            tag = get_object_or_404(models.Tag, name=pk, pk__in=repository_version.content)
            manifest = tag.tagged_manifest
        else:
            manifest = get_object_or_404(models.Manifest, digest=pk,
                                         pk__in=repository_version.content)

        return ManifestResponse(manifest, path, request)

    def get(self, request, path, pk=None):
        """
        Responds to GET requests about manifests by reference
        :param request:
        :param path:
        :param digest:
        :return:
        """
        distribution = get_object_or_404(models.ContainerDistribution, base_path=path)
        if distribution.repository:
            repository = distribution.repository
            repository_version = repository.latest_version()
        elif distribution.repository_version:
            repository_version = distribution.repository_version
        else:
            raise Http404("Repository {} does not exist.".format(path))
        if pk[:7] != 'sha256:':
            tag = get_object_or_404(models.Tag, name=pk, pk__in=repository_version.content)
            manifest = tag.tagged_manifest
        else:
            manifest = get_object_or_404(models.Manifest, digest=pk,
                                         pk__in=repository_version.content)

        return HttpResponseRedirect("{}/pulp/container/{}/manifests/{}".format(
            settings.CONTENT_ORIGIN, path, manifest.digest))

    def put(self, request, path, pk=None):
        """
        Responds with the actual manifest
        :param request:
        :param path:
        :param pk:
        :return:
        """
        distribution = get_object_or_404(models.ContainerDistribution, base_path=path)
        if distribution.repository:
            repository = distribution.repository
        else:
            raise Http404("Repository {} does not exist.".format(path))

        # iterate over all the layers and create
        chunk = request.META['wsgi.input']
        artifact = self.receive_artifact(chunk)
        with storage.open(artifact.file.name) as artifact_file:
            raw_data = artifact_file.read()
        content_data = json.loads(raw_data)
        config_layer = content_data.get('config')
        config_blob = models.Blob.objects.get(digest=config_layer.get('digest'))

        manifest = models.Manifest(digest="sha256:{id}".format(id=artifact.sha256),
                                   schema_version=2, media_type=request.content_type,
                                   config_blob=config_blob)
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
            blobs.append(layer.get('digest'))
        blobs_qs = models.Blob.objects.filter(digest__in=blobs)
        thru = []
        for blob in blobs_qs:
            thru.append(models.BlobManifest(manifest=manifest, manifest_blob=blob))
        models.BlobManifest.objects.bulk_create(objs=thru,
                                                ignore_conflicts=True,
                                                batch_size=1000)
        tag = models.Tag(name=pk, tagged_manifest=manifest)
        try:
            tag.save()
        except IntegrityError:
            pass
        with repository.new_version() as new_version:
            new_version.add_content(models.Manifest.objects.filter(digest=manifest.digest))
            new_version.remove_content(models.Tag.objects.filter(name=tag.name))
            new_version.add_content(models.Tag.objects.filter(name=tag.name,
                                                              tagged_manifest=manifest))
        return ManifestResponse(manifest, path, request, status=201)

    def receive_artifact(self, chunk):
        """Handles assembling of Manifest as it's being uploaded."""
        with NamedTemporaryFile('ab') as temp_file:
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

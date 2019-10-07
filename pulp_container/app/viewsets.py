"""
Check `Plugin Writer's Guide`_ for more details.

. _Plugin Writer's Guide:
    http://docs.pulpproject.org/en/3.0/nightly/plugins/plugin-writer/index.html
"""

from django_filters import MultipleChoiceFilter
from drf_yasg.utils import swagger_auto_schema
from pulpcore.plugin.serializers import (
    AsyncOperationResponseSerializer,
    RepositorySyncURLSerializer,
)
from pulpcore.plugin.models import Content
from pulpcore.plugin.tasking import enqueue_with_reservation
from pulpcore.plugin.viewsets import (
    BaseDistributionViewSet,
    CharInFilter,
    ContentFilter,
    NamedModelViewSet,
    ReadOnlyContentViewSet,
    RemoteViewSet,
    OperationPostponedResponse,
)
from rest_framework import viewsets as drf_viewsets
from rest_framework.decorators import action

from . import models, serializers, tasks


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

    # This decorator is necessary since a sync operation is asyncrounous and returns
    # the id and href of the sync task.
    @swagger_auto_schema(
        operation_description="Trigger an asynchronous task to sync content.",
        responses={202: AsyncOperationResponseSerializer}
    )
    @action(detail=True, methods=['post'], serializer_class=RepositorySyncURLSerializer)
    def sync(self, request, pk):
        """
        Synchronizes a repository. The ``repository`` field has to be provided.
        """
        remote = self.get_object()
        serializer = RepositorySyncURLSerializer(data=request.data, context={'request': request})

        # Validate synchronously to return 400 errors.
        serializer.is_valid(raise_exception=True)
        repository = serializer.validated_data.get('repository')
        result = enqueue_with_reservation(
            tasks.synchronize,
            [repository, remote],
            kwargs={
                'remote_pk': remote.pk,
                'repository_pk': repository.pk
            }
        )
        return OperationPostponedResponse(result, request)


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


class TagImageViewSet(drf_viewsets.ViewSet):
    """
    ViewSet used for tagging manifests. This endpoint supports only HTTP POST requests.
    """

    endpoint_name = 'tag'

    @swagger_auto_schema(
        operation_description="Trigger an asynchronous task to create a new repository",
        responses={202: AsyncOperationResponseSerializer},
        request_body=serializers.TagImageSerializer,
    )
    def create(self, request):
        """
        Create a task which is responsible for initializing a new repository version.
        """
        serializer = serializers.TagImageSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        manifest = serializer.validated_data['manifest']
        tag = serializer.validated_data['tag']
        repository = serializer.validated_data['repository']

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


class UnTagImageViewSet(drf_viewsets.ViewSet):
    """
    ViewSet used for untagging manifests. This endpoint supports only HTTP POST requests.
    """

    endpoint_name = 'untag'

    @swagger_auto_schema(
        operation_description="Trigger an asynchronous task to create a new repository",
        responses={202: AsyncOperationResponseSerializer},
        request_body=serializers.UnTagImageSerializer,
    )
    def create(self, request):
        """
        Create a task which is responsible for creating a new tag.
        """
        serializer = serializers.UnTagImageSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)

        tag = serializer.validated_data['tag']
        repository = serializer.validated_data['repository']

        result = enqueue_with_reservation(
            tasks.untag_image,
            [repository],
            kwargs={
                'tag': tag,
                'repository_pk': repository.pk
            }
        )
        return OperationPostponedResponse(result, request)


class RecursiveAdd(drf_viewsets.ViewSet):
    """
    ViewSet for recursively adding Container content.
    """

    serializer_class = serializers.RecursiveManageSerializer

    @swagger_auto_schema(
        operation_description="Trigger an asynchronous task to recursively add container content.",
        responses={202: AsyncOperationResponseSerializer},
        request_body=serializers.RecursiveManageSerializer,
    )
    def create(self, request):
        """
        Queues a task that creates a new RepositoryVersion by adding content units.
        """
        add_content_units = []
        serializer = serializers.RecursiveManageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        repository = serializer.validated_data['repository']

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


class TagCopyViewSet(drf_viewsets.ViewSet):
    """
    ViewSet for copying tags recursively.
    """

    serializer_class = serializers.TagCopySerializer

    @swagger_auto_schema(
        operation_description="Trigger an asynchronous task to copy tags",
        responses={202: AsyncOperationResponseSerializer},
        request_body=serializers.TagCopySerializer,
    )
    def create(self, request):
        """
        Queues a task that creates a new RepositoryVersion by adding content units.
        """
        names = request.data.get("names")
        serializer = serializers.TagCopySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        source_latest = serializer.validated_data['source_repository_version']
        destination = serializer.validated_data['destination_repository']
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
            tasks.recursive_add_content, [destination],
            kwargs={
                'repository_pk': destination.pk,
                'content_units': tags_to_add.values_list('pk', flat=True),
            }
        )
        return OperationPostponedResponse(result, request)


class ManifestCopyViewSet(drf_viewsets.ViewSet):
    """
    ViewSet for copying manifests recursively.
    """

    serializer_class = serializers.ManifestCopySerializer

    @swagger_auto_schema(
        operation_description="Trigger an asynchronous task to copy manifests",
        responses={202: AsyncOperationResponseSerializer},
        request_body=serializers.ManifestCopySerializer,
    )
    def create(self, request):
        """
        Queues a task that creates a new RepositoryVersion by adding content units.
        """
        serializer = serializers.ManifestCopySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        source_latest = serializer.validated_data['source_repository_version']
        destination = serializer.validated_data['destination_repository']
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
            tasks.recursive_add_content, [destination],
            kwargs={
                'repository_pk': destination.pk,
                'content_units': manifests_to_add,
            }
        )
        return OperationPostponedResponse(result, request)


class RecursiveRemove(drf_viewsets.ViewSet):
    """
    ViewSet for recursively removing Container content.
    """

    serializer_class = serializers.RecursiveManageSerializer

    @swagger_auto_schema(
        operation_description="Trigger an async task to recursively remove container content.",
        responses={202: AsyncOperationResponseSerializer},
        request_body=serializers.RecursiveManageSerializer,
    )
    def create(self, request):
        """
        Queues a task that creates a new RepositoryVersion by removing content units.
        """
        remove_content_units = []
        serializer = serializers.RecursiveManageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        repository = serializer.validated_data['repository']

        if 'content_units' in request.data:
            for url in request.data['content_units']:
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

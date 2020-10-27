"""
Check `Plugin Writer's Guide`_ for more details.

. _Plugin Writer's Guide:
    http://docs.pulpproject.org/plugins/plugin-writer/index.html
"""
import logging

from django.db import IntegrityError
from django_filters import CharFilter, MultipleChoiceFilter
from drf_spectacular.utils import extend_schema
from rest_framework import mixins

from pulpcore.plugin.serializers import (
    AsyncOperationResponseSerializer,
    RepositorySyncURLSerializer,
)
from pulpcore.plugin.models import Artifact, Content
from pulpcore.plugin.tasking import enqueue_with_reservation
from pulpcore.plugin.viewsets import (
    BaseDistributionViewSet,
    CharInFilter,
    ContentFilter,
    ContentGuardViewSet,
    # TODO: DistributionFilter,
    ImmutableRepositoryViewSet,
    NamedModelViewSet,
    ReadOnlyContentViewSet,
    RemoteViewSet,
    RepositoryViewSet,
    RepositoryVersionViewSet,
    OperationPostponedResponse,
)
from rest_framework.decorators import action

from pulp_container.app import models, serializers, tasks


log = logging.getLogger(__name__)


class TagFilter(ContentFilter):
    """
    FilterSet for Tags.
    """

    media_type = MultipleChoiceFilter(
        choices=models.Manifest.MANIFEST_CHOICES,
        field_name="tagged_manifest__media_type",
        lookup_expr="contains",
    )
    digest = CharInFilter(field_name="tagged_manifest__digest", lookup_expr="in")

    class Meta:
        model = models.Tag
        fields = {
            "name": ["exact", "in"],
        }


class ManifestFilter(ContentFilter):
    """
    FilterSet for Manifests.
    """

    media_type = MultipleChoiceFilter(choices=models.Manifest.MANIFEST_CHOICES)

    class Meta:
        model = models.Manifest
        fields = {
            "digest": ["exact", "in"],
        }


class BlobFilter(ContentFilter):
    """
    FilterSet for Blobs.
    """

    media_type = MultipleChoiceFilter(choices=models.Blob.BLOB_CHOICES)

    class Meta:
        model = models.Blob
        fields = {
            "digest": ["exact", "in"],
        }


# TODO: class ContainerDistributionFilter(DistributionFilter):
class ContainerDistributionFilter(BaseDistributionViewSet.filterset_class):
    """
    FilterSet for ContainerDistributions
    """

    namespace__name = CharFilter(lookup_expr="exact")

    class Meta:
        model = models.ContainerDistribution
        fields = BaseDistributionViewSet.filterset_class.Meta.fields


class TagViewSet(ReadOnlyContentViewSet):
    """
    ViewSet for Tag.
    """

    endpoint_name = "tags"
    queryset = models.Tag.objects.all()
    serializer_class = serializers.TagSerializer
    filterset_class = TagFilter


class ManifestViewSet(ReadOnlyContentViewSet):
    """
    ViewSet for Manifest.
    """

    endpoint_name = "manifests"
    queryset = models.Manifest.objects.all()
    serializer_class = serializers.ManifestSerializer
    filterset_class = ManifestFilter


class BlobViewSet(ReadOnlyContentViewSet):
    """
    ViewSet for Blobs.
    """

    endpoint_name = "blobs"
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

    endpoint_name = "container"
    queryset = models.ContainerRemote.objects.all()
    serializer_class = serializers.ContainerRemoteSerializer


class ContainerRepositoryViewSet(RepositoryViewSet):
    """
    ViewSet for container repo.
    """

    endpoint_name = "container"
    queryset = models.ContainerRepository.objects.all()
    serializer_class = serializers.ContainerRepositorySerializer

    # This decorator is necessary since a sync operation is asyncrounous and returns
    # the id and href of the sync task.
    @extend_schema(
        description="Trigger an asynchronous task to sync content.",
        summary="Sync from a remote",
        responses={202: AsyncOperationResponseSerializer},
    )
    @action(detail=True, methods=["post"], serializer_class=RepositorySyncURLSerializer)
    def sync(self, request, pk):
        """
        Synchronizes a repository. The ``repository`` field has to be provided.
        """
        repository = self.get_object()
        serializer = RepositorySyncURLSerializer(data=request.data, context={"request": request})

        # Validate synchronously to return 400 errors.
        serializer.is_valid(raise_exception=True)
        remote = serializer.validated_data.get("remote")
        mirror = serializer.validated_data.get("mirror")

        result = enqueue_with_reservation(
            tasks.synchronize,
            [repository, remote],
            kwargs={"remote_pk": remote.pk, "repository_pk": repository.pk, "mirror": mirror},
        )
        return OperationPostponedResponse(result, request)

    @extend_schema(
        description="Trigger an asynchronous task to tag an image in the repository",
        summary="Create a Tag",
        responses={202: AsyncOperationResponseSerializer},
        request=serializers.TagImageSerializer,
    )
    @action(detail=True, methods=["post"], serializer_class=serializers.TagImageSerializer)
    def tag(self, request, pk):
        """
        Create a task which is responsible for creating a new tag.
        """
        repository = self.get_object()
        request.data["repository"] = repository

        serializer = serializers.TagImageSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        manifest = serializer.validated_data["manifest"]
        tag = serializer.validated_data["tag"]

        result = enqueue_with_reservation(
            tasks.tag_image,
            [repository, manifest],
            kwargs={"manifest_pk": manifest.pk, "tag": tag, "repository_pk": repository.pk},
        )
        return OperationPostponedResponse(result, request)

    @extend_schema(
        description="Trigger an asynchronous task to untag an image in the repository",
        summary="Delete a tag",
        responses={202: AsyncOperationResponseSerializer},
        request=serializers.UnTagImageSerializer,
    )
    @action(detail=True, methods=["post"], serializer_class=serializers.UnTagImageSerializer)
    def untag(self, request, pk):
        """
        Create a task which is responsible for untagging an image.
        """
        repository = self.get_object()
        request.data["repository"] = repository

        serializer = serializers.UnTagImageSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        tag = serializer.validated_data["tag"]

        result = enqueue_with_reservation(
            tasks.untag_image, [repository], kwargs={"tag": tag, "repository_pk": repository.pk}
        )
        return OperationPostponedResponse(result, request)

    @extend_schema(
        description="Trigger an asynchronous task to recursively add container content.",
        summary="Add content",
        responses={202: AsyncOperationResponseSerializer},
        request=serializers.RecursiveManageSerializer,
    )
    @action(detail=True, methods=["post"], serializer_class=serializers.RecursiveManageSerializer)
    def add(self, request, pk):
        """
        Queues a task that creates a new RepositoryVersion by adding content units.
        """
        add_content_units = []
        repository = self.get_object()
        serializer = serializers.RecursiveManageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if "content_units" in request.data:
            for url in request.data["content_units"]:
                content = NamedModelViewSet.get_resource(url, Content)
                add_content_units.append(content.pk)

        result = enqueue_with_reservation(
            tasks.recursive_add_content,
            [repository],
            kwargs={"repository_pk": repository.pk, "content_units": add_content_units},
        )
        return OperationPostponedResponse(result, request)

    @extend_schema(
        description="Trigger an async task to recursively remove container content.",
        summary="Remove content",
        responses={202: AsyncOperationResponseSerializer},
        request=serializers.RecursiveManageSerializer,
    )
    @action(detail=True, methods=["post"], serializer_class=serializers.RecursiveManageSerializer)
    def remove(self, request, pk):
        """
        Queues a task that creates a new RepositoryVersion by removing content units.
        """
        remove_content_units = []
        repository = self.get_object()
        serializer = serializers.RecursiveManageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if "content_units" in request.data:
            for url in request.data["content_units"]:
                if url == "*":
                    remove_content_units = [url]
                    break

                content = NamedModelViewSet.get_resource(url, Content)
                remove_content_units.append(content.pk)

        result = enqueue_with_reservation(
            tasks.recursive_remove_content,
            [repository],
            kwargs={"repository_pk": repository.pk, "content_units": remove_content_units},
        )
        return OperationPostponedResponse(result, request)

    @extend_schema(
        description="Trigger an asynchronous task to copy tags",
        summary="Copy tags",
        responses={202: AsyncOperationResponseSerializer},
        request=serializers.TagCopySerializer,
    )
    @action(detail=True, methods=["post"], serializer_class=serializers.TagCopySerializer)
    def copy_tags(self, request, pk):
        """
        Queues a task that creates a new RepositoryVersion by adding Tags.
        """
        names = request.data.get("names")
        serializer = serializers.TagCopySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        repository = self.get_object()
        source_latest = serializer.validated_data["source_repository_version"]
        content_tags_in_repo = source_latest.content.filter(pulp_type="container.tag")
        tags_in_repo = models.Tag.objects.filter(pk__in=content_tags_in_repo)
        if names is None:
            tags_to_add = tags_in_repo
        else:
            tags_to_add = tags_in_repo.filter(name__in=names)

        result = enqueue_with_reservation(
            tasks.recursive_add_content,
            [repository],
            kwargs={
                "repository_pk": repository.pk,
                "content_units": tags_to_add.values_list("pk", flat=True),
            },
        )
        return OperationPostponedResponse(result, request)

    @extend_schema(
        description="Trigger an asynchronous task to copy manifests",
        summary="Copy manifests",
        responses={202: AsyncOperationResponseSerializer},
        request=serializers.ManifestCopySerializer,
    )
    @action(detail=True, methods=["post"], serializer_class=serializers.ManifestCopySerializer)
    def copy_manifests(self, request, pk):
        """
        Queues a task that creates a new RepositoryVersion by adding Manifests.
        """
        serializer = serializers.ManifestCopySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        repository = self.get_object()
        source_latest = serializer.validated_data["source_repository_version"]
        content_manifests_in_repo = source_latest.content.filter(pulp_type="container.manifest")
        manifests_in_repo = models.Manifest.objects.filter(pk__in=content_manifests_in_repo)
        digests = request.data.get("digests")
        media_types = request.data.get("media_types")
        filters = {}
        if digests is not None:
            filters["digest__in"] = digests
        if media_types is not None:
            filters["media_type__in"] = media_types
        manifests_to_add = manifests_in_repo.filter(**filters)
        result = enqueue_with_reservation(
            tasks.recursive_add_content,
            [repository],
            kwargs={"repository_pk": repository.pk, "content_units": manifests_to_add},
        )
        return OperationPostponedResponse(result, request)

    @extend_schema(
        description="Trigger an asynchronous task to build an OCI image from a "
        "Containerfile. A new repository version is created with the new "
        "image and tag. This API is tech preview in Pulp Container 1.1. "
        "Backwards compatibility when upgrading is not guaranteed.",
        summary="Build an Image",
        responses={202: AsyncOperationResponseSerializer},
        request=serializers.OCIBuildImageSerializer,
    )
    @action(detail=True, methods=["post"], serializer_class=serializers.TagImageSerializer)
    def build_image(self, request, pk):
        """
        Create a task which is responsible for creating a new image and tag.
        """
        repository = self.get_object()

        serializer = serializers.OCIBuildImageSerializer(
            data=request.data, context={"request": request}
        )

        serializer.is_valid(raise_exception=True)

        containerfile = serializer.validated_data["containerfile_artifact"]
        try:
            containerfile.save()
        except IntegrityError:
            containerfile = Artifact.objects.get(sha256=containerfile.sha256)
        tag = serializer.validated_data["tag"]

        artifacts = serializer.validated_data["artifacts"]

        result = enqueue_with_reservation(
            tasks.build_image_from_containerfile,
            [repository],
            kwargs={
                "containerfile_pk": containerfile.pk,
                "tag": tag,
                "repository_pk": repository.pk,
                "artifacts": artifacts,
            },
        )
        return OperationPostponedResponse(result, request)


class ContainerRepositoryVersionViewSet(RepositoryVersionViewSet):
    """
    ContainerRepositoryVersion represents a single container repository version.
    """

    parent_viewset = ContainerRepositoryViewSet


class ContainerPushRepositoryViewSet(ImmutableRepositoryViewSet):
    """
    ViewSet for a container push repository.
    """

    endpoint_name = "container-push"
    queryset = models.ContainerPushRepository.objects.all()
    serializer_class = serializers.ContainerPushRepositorySerializer

    @extend_schema(
        description="Trigger an asynchronous delete task",
        responses={202: AsyncOperationResponseSerializer},
    )
    def destroy(self, request, pk, **kwargs):
        """
        Delete a push repository with its distribution
        """
        repository = self.get_object()
        distribution = models.ContainerDistribution.objects.get(repository_id=repository.pk)
        async_result = enqueue_with_reservation(
            tasks.general_multi_delete,
            [distribution, repository],
            args=(
                [
                    (distribution.pk, "container", "ContainerDistributionSerializer"),
                    (distribution.repository.pk, "container", "ContainerPushRepositorySerializer"),
                ],
            ),
        )
        return OperationPostponedResponse(async_result, request)


class ContainerPushRepositoryVersionViewSet(RepositoryVersionViewSet):
    """
    ContainerPushRepositoryVersion represents a single container push repository version.
    """

    parent_viewset = ContainerPushRepositoryViewSet


class ContainerDistributionViewSet(BaseDistributionViewSet):
    """
    The Container Distribution will serve the latest version of a Repository if
    ``repository`` is specified. The Container Distribution will serve a specific
    repository version if ``repository_version``. Note that **either**
    ``repository`` or ``repository_version`` can be set on a Container
    Distribution, but not both.
    """

    endpoint_name = "container"
    queryset = models.ContainerDistribution.objects.all()
    serializer_class = serializers.ContainerDistributionSerializer
    filterset_class = ContainerDistributionFilter

    @extend_schema(
        description="Trigger an asynchronous delete task",
        responses={202: AsyncOperationResponseSerializer},
    )
    def destroy(self, request, pk, **kwargs):
        """
        Delete a distribution. If a push repository is associated to it, delete it as well.
        """
        distribution = self.get_object()
        reservations = [distribution]
        instance_ids = [
            (distribution.pk, "container", "ContainerDistributionSerializer"),
        ]
        if distribution.repository and distribution.repository.cast().PUSH_ENABLED:
            reservations.append(distribution.repository)
            instance_ids.append(
                (distribution.repository.pk, "container", "ContainerPushRepositorySerializer"),
            )

        async_result = enqueue_with_reservation(
            tasks.general_multi_delete, reservations, args=(instance_ids,)
        )
        return OperationPostponedResponse(async_result, request)


class ContentRedirectContentGuardViewSet(ContentGuardViewSet):
    """
    Content guard to protect preauthenticated redirects to the content app.
    """

    endpoint_name = "content_redirect"
    queryset = models.ContentRedirectContentGuard.objects.all()
    serializer_class = serializers.ContentRedirectContentGuardSerializer


class ContainerNamespaceViewSet(
    NamedModelViewSet,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
):
    """
    ViewSet for ContainerNamespaces.
    """

    endpoint_name = "pulp_container/namespaces"
    queryset = models.ContainerNamespace.objects.all()
    serializer_class = serializers.ContainerNamespaceSerializer

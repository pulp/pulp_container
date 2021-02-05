"""
Check `Plugin Writer's Guide`_ for more details.

. _Plugin Writer's Guide:
    http://docs.pulpproject.org/plugins/plugin-writer/index.html
"""
import logging

from gettext import gettext as _

from django.db import IntegrityError
from django.db.models import Q
from django.http import Http404
from django_filters import CharFilter, MultipleChoiceFilter
from guardian.shortcuts import get_objects_for_user
from drf_spectacular.utils import extend_schema
from rest_framework import mixins
from rest_framework.decorators import action

from pulpcore.plugin.access_policy import AccessPolicyFromDB
from pulpcore.plugin.serializers import (
    AsyncOperationResponseSerializer,
    RepositorySyncURLSerializer,
)
from pulpcore.plugin.models import Artifact, Content
from pulpcore.plugin.tasking import enqueue_with_reservation
from pulpcore.plugin.viewsets import (
    BaseDistributionViewSet,
    BaseFilterSet,
    CharInFilter,
    ContentFilter,
    ContentGuardViewSet,
    # TODO: DistributionFilter,
    NamedModelViewSet,
    NAME_FILTER_OPTIONS,
    ReadOnlyContentViewSet,
    ReadOnlyRepositoryViewSet,
    RemoteViewSet,
    RepositoryViewSet,
    RepositoryVersionViewSet,
    OperationPostponedResponse,
)

from pulp_container.app import access_policy, models, serializers, tasks


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


class ContainerNamespaceFilter(BaseFilterSet):
    """
    FilterSet for ContainerNamespaces
    """

    class Meta:
        model = models.ContainerNamespace
        fields = {
            "name": NAME_FILTER_OPTIONS,
        }


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
    permission_classes = (AccessPolicyFromDB,)
    queryset_filtering_required_permission = "container.view_containerremote"

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list"],
                "principal": "authenticated",
                "effect": "allow",
            },
            {
                "action": ["create"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_perms:container.add_containerremote",
            },
            {
                "action": ["retrieve"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_or_obj_perms:container.view_containerremote",
            },
            {
                "action": ["update", "partial_update"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_or_obj_perms:container.change_containerremote",
            },
            {
                "action": ["destroy"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_or_obj_perms:container.delete_containerremote",
            },
        ],
        "permissions_assignment": [
            {
                "function": "add_for_object_creator",
                "parameters": None,
                "permissions": [
                    "container.view_containerremote",
                    "container.change_containerremote",
                    "container.delete_containerremote",
                ],
            },
        ],
    }


class TagOperationsMixin:
    """
    A mixin that adds functionality for creating and deleting tags.
    """

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


class RepositoryVersionQuerySetMixin:
    """
    A mixin which provides with a custom `get_queryset` method for repository version viewsets.
    """

    def get_queryset(self):
        """
        Gets a QuerySet based on the current request.

        Filtered by a permission for a corresponding repository.

        Returns:
            django.db.models.query.QuerySet: The queryset returned by the superclass filtered by
                the permission for a corresponding repository.

        """
        qs = super().get_queryset()
        try:
            perm = self.queryset_filtering_required_repo_permission
        except AttributeError:
            pass
        else:
            repo_version = qs.first()
            repo = repo_version.repository.cast()
            if not (self.request.user.has_perm(perm) or self.request.user.has_perm(perm, repo)):
                raise Http404(_("detail not found"))
        return qs


class ContainerRepositoryViewSet(TagOperationsMixin, RepositoryViewSet):
    """
    ViewSet for container repo.
    """

    endpoint_name = "container"
    queryset = models.ContainerRepository.objects.all()
    serializer_class = serializers.ContainerRepositorySerializer
    permission_classes = (AccessPolicyFromDB,)
    queryset_filtering_required_permission = "container.view_containerrepository"
    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list"],
                "principal": "authenticated",
                "effect": "allow",
            },
            {
                "action": ["create"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_perms:container.add_containerrepository",
            },
            {
                "action": ["retrieve"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_or_obj_perms:container.view_containerrepository",
            },
            {
                "action": ["destroy"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_or_obj_perms:container.delete_containerrepository",
            },
            {
                "action": ["update", "partial_update"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_or_obj_perms:container.change_containerrepository",
            },
            {
                "action": ["sync"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_obj_perms:container.sync_containerrepository",
                    "has_remote_param_model_or_obj_perms:container.view_containerremote",
                ],
            },
            {
                "action": ["add", "remove", "tag", "untag", "copy_tags", "copy_manifests"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_obj_perms:container.modify_content_containerrepository",
                ],
            },
            {
                "action": ["build_image"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_obj_perms:container.build_image_containerrepository",
                ],
            },
        ],
        "permissions_assignment": [
            {
                "function": "add_for_object_creator",
                "parameters": None,
                "permissions": [
                    "container.view_containerrepository",
                    "container.change_containerrepository",
                    "container.delete_containerrepository",
                    "container.delete_containerrepository_versions",
                    "container.sync_containerrepository",
                    "container.modify_content_containerrepository",
                    "container.build_image_containerrepository",
                ],
            },
        ],
    }

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


class ContainerRepositoryVersionViewSet(RepositoryVersionQuerySetMixin, RepositoryVersionViewSet):
    """
    ContainerRepositoryVersion represents a single container repository version.
    """

    parent_viewset = ContainerRepositoryViewSet
    permission_classes = (AccessPolicyFromDB,)
    queryset_filtering_required_repo_permission = "container.view_containerrepository"

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list"],
                "principal": "authenticated",
                "effect": "allow",
            },
            {
                "action": ["retrieve"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_repo_attr_model_or_obj_perms:container.view_containerrepository",
            },
            {
                "action": ["destroy"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_repo_attr_model_or_obj_perms:container.delete_containerrepository_versions",  # noqa
                    "has_repo_attr_model_or_obj_perms:container.view_containerrepository",
                ],
            },
            {
                "action": ["destroy"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_repo_attr_model_or_obj_perms:container.delete_containerrepository",
                    "has_repo_attr_model_or_obj_perms:container.view_containerrepository",
                ],
            },
        ],
    }


class ContainerPushRepositoryViewSet(TagOperationsMixin, ReadOnlyRepositoryViewSet):
    """
    ViewSet for a container push repository.

    POST and DELETE are disallowed because a push repository is tightly coupled with a
    ContainerDistribution which handles it automatically.
    Created - during push operation, removed - with ContainerDistribution removal.
    """

    endpoint_name = "container-push"
    queryset = models.ContainerPushRepository.objects.all()
    serializer_class = serializers.ContainerPushRepositorySerializer
    permission_classes = (access_policy.NamespaceAccessPolicyFromDB,)

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list"],
                "principal": "authenticated",
                "effect": "allow",
            },
            {
                "action": ["retrieve"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_namespace_or_obj_perms:container.view_containerpushrepository",
            },
            {
                "action": ["tag", "untag"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_namespace_or_obj_perms:container.modify_content_containerpushrepository",
                ],
            },
        ],
        "permissions_assignment": [
            {
                "function": "add_perms_to_distribution_group",
                "parameters": {
                    "group_type": "owners",
                    "add_user_to_group": True,
                },
                "permissions": [
                    "container.view_containerpushrepository",
                    "container.modify_content_containerpushrepository",
                ],
            },
            {
                "function": "add_perms_to_distribution_group",
                "parameters": {
                    "group_type": "collaborators",
                    "add_user_to_group": False,
                },
                "permissions": [
                    "container.view_containerpushrepository",
                    "container.modify_content_containerpushrepository",
                ],
            },
            {
                "function": "add_perms_to_distribution_group",
                "parameters": {
                    "group_type": "consumers",
                    "add_user_to_group": False,
                },
                "permissions": [
                    "container.view_containerpushrepository",
                ],
            },
        ],
    }

    def get_queryset(self):
        """
        Returns a queryset by filtering by namespace permission to view distributions and
        distribution level permissions.
        """

        qs = models.ContainerPushRepository.objects.all()
        namespaces = get_objects_for_user(self.request.user, "container.view_containernamespace")
        ns_repository_pks = models.ContainerDistribution.objects.filter(
            namespace__in=namespaces
        ).values_list("repository")
        dist_repository_pks = get_objects_for_user(
            self.request.user, "container.view_containerdistribution"
        ).values_list("repository")
        public_repository_pks = models.ContainerDistribution.objects.filter(
            private=False
        ).values_list("repository")
        return qs.filter(
            Q(pk__in=ns_repository_pks)
            | Q(pk__in=dist_repository_pks)
            | Q(pk__in=public_repository_pks)
        )


class ContainerPushRepositoryVersionViewSet(
    RepositoryVersionQuerySetMixin,
    RepositoryVersionViewSet,
):
    """
    ContainerPushRepositoryVersion represents a single container push repository version.

    Repository versions of a push repository are not allowed to be deleted. Versioning of such
    repositories, as well as creation/removal, happens automatically without explicit user actions.
    Users could make a repository not functional by accident if allowed to delete repository
    versions.
    """

    parent_viewset = ContainerPushRepositoryViewSet
    permission_classes = (AccessPolicyFromDB,)
    queryset_filtering_required_repo_permission = "container.view_containerpushrepository"

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list"],
                "principal": "authenticated",
                "effect": "allow",
            },
            {
                "action": ["retrieve"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_repo_attr_model_or_obj_perms:container.view_containerpushrepository",  # noqa
            },
        ],
    }


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
    permission_classes = (access_policy.NamespaceAccessPolicyFromDB,)

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list"],
                "principal": "authenticated",
                "effect": "allow",
            },
            {
                "action": ["catalog"],
                "principal": "authenticated",
                "effect": "allow",
            },
            {
                "action": ["create"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_perms:container.add_containerdistribution",
            },
            {
                "action": ["retrieve"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_namespace_or_obj_perms:container.view_containerdistribution",
                ],
            },
            {
                "action": ["pull"],
                "principal": "*",
                "effect": "allow",
                "condition": [
                    "not is_private",
                ],
            },
            {
                "action": ["pull"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_namespace_or_obj_perms:container.pull_containerdistribution",
                ],
            },
            {
                "action": ["update", "partial_update"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_obj_perms:container.change_containerdistribution",
                ],
            },
            {
                "action": ["push"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_namespace_or_obj_perms:container.push_containerdistribution",
                    "obj_exists",
                ],
            },
            {
                "action": ["push"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_namespace_or_obj_perms:container.add_containerdistribution",
                    "has_namespace_or_obj_perms:container.push_containerdistribution",
                ],
            },
            {
                "action": ["destroy"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_namespace_or_obj_perms:container.delete_containerdistribution",
                ],
            },
        ],
        "permissions_assignment": [
            {
                "function": "create_distribution_group",
                "parameters": {
                    "group_type": "owners",
                    "add_user_to_group": True,
                },
                "permissions": [
                    "container.view_containerdistribution",
                    "container.pull_containerdistribution",
                    "container.push_containerdistribution",
                    "container.delete_containerdistribution",
                    "container.change_containerdistribution",
                ],
            },
            {
                "function": "add_push_repository_perms_to_distribution_group",
                "parameters": {
                    "group_type": "owners",
                },
                "permissions": [
                    "container.view_containerpushrepository",
                    "container.modify_content_containerpushrepository",
                ],
            },
            {
                "function": "create_distribution_group",
                "parameters": {
                    "group_type": "collaborators",
                    "add_user_to_group": False,
                },
                "permissions": [
                    "container.view_containerdistribution",
                    "container.pull_containerdistribution",
                    "container.push_containerdistribution",
                ],
            },
            {
                "function": "add_push_repository_perms_to_distribution_group",
                "parameters": {
                    "group_type": "collaborators",
                },
                "permissions": [
                    "container.view_containerpushrepository",
                    "container.modify_content_containerpushrepository",
                ],
            },
            {
                "function": "create_distribution_group",
                "parameters": {
                    "group_type": "consumers",
                    "add_user_to_group": False,
                },
                "permissions": [
                    "container.view_containerdistribution",
                    "container.pull_containerdistribution",
                ],
            },
            {
                "function": "add_push_repository_perms_to_distribution_group",
                "parameters": {
                    "group_type": "consumers",
                },
                "permissions": [
                    "container.view_containerpushrepository",
                ],
            },
        ],
    }

    def get_queryset(self):
        """
        Returns a queryset of distributions filtered by namespace permissions and public status.
        """

        public_qs = models.ContainerDistribution.objects.filter(private=False)
        obj_perm_qs = get_objects_for_user(
            self.request.user, "container.view_containerdistribution"
        )
        namespaces = get_objects_for_user(self.request.user, "container.view_containernamespace")
        namespaces |= get_objects_for_user(
            self.request.user, "container.namespace_view_containerdistribution"
        )
        ns_qs = models.ContainerDistribution.objects.filter(namespace__in=namespaces)
        return public_qs | obj_perm_qs | ns_qs

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
    filterset_class = ContainerNamespaceFilter
    permission_classes = (AccessPolicyFromDB,)
    queryset_filtering_required_permission = "container.view_containernamespace"

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list"],
                "principal": "authenticated",
                "effect": "allow",
            },
            {
                "action": ["create"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_perms:container.add_containernamespace",
            },
            {
                "action": ["retrieve"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_or_obj_perms:container.view_containernamespace",
            },
            {
                "action": ["destroy"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_or_obj_perms:container.delete_containernamespace",
            },
            {
                "action": ["create_distribution"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_or_obj_perms:container.namespace_add_containerdistribution",
            },
            {
                "action": ["view_distribution"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_or_obj_perms:container.namespace_view_containerdistribution",  # noqa: E501
            },
        ],
        "permissions_assignment": [
            {
                "function": "create_namespace_group",
                "parameters": {
                    "group_type": "owners",
                    "add_user_to_group": True,
                },
                "permissions": [
                    "container.view_containernamespace",
                    "container.delete_containernamespace",
                    "container.namespace_add_containerdistribution",
                    "container.namespace_delete_containerdistribution",
                    "container.namespace_view_containerdistribution",
                    "container.namespace_pull_containerdistribution",
                    "container.namespace_push_containerdistribution",
                    "container.namespace_change_containerdistribution",
                    "container.namespace_view_containerpushrepository",
                    "container.namespace_modify_content_containerpushrepository",
                ],
            },
            {
                "function": "create_namespace_group",
                "parameters": {
                    "group_type": "collaborators",
                    "add_user_to_group": False,
                },
                "permissions": [
                    "container.view_containernamespace",
                    "container.namespace_add_containerdistribution",
                    "container.namespace_delete_containerdistribution",
                    "container.namespace_view_containerdistribution",
                    "container.namespace_pull_containerdistribution",
                    "container.namespace_push_containerdistribution",
                    "container.namespace_change_containerdistribution",
                    "container.namespace_view_containerpushrepository",
                    "container.namespace_modify_content_containerpushrepository",
                ],
            },
            {
                "function": "create_namespace_group",
                "parameters": {
                    "group_type": "consumers",
                    "add_user_to_group": False,
                },
                "permissions": [
                    "container.view_containernamespace",
                    "container.namespace_view_containerdistribution",
                    "container.namespace_pull_containerdistribution",
                    "container.namespace_view_containerpushrepository",
                ],
            },
        ],
    }

    @extend_schema(
        description="Trigger an asynchronous delete task",
        responses={202: AsyncOperationResponseSerializer},
    )
    def destroy(self, request, pk, **kwargs):
        """
        Delete a Namespace with all distributions.
        If a push repository is associated to any of its distributions, delete it as well.
        """
        namespace = self.get_object()
        reservations = []
        instance_ids = []

        for distribution in namespace.container_distributions.all():

            reservations.append(distribution)
            instance_ids.append(
                (distribution.pk, "container", "ContainerDistributionSerializer"),
            )
            if distribution.repository and distribution.repository.cast().PUSH_ENABLED:
                reservations.append(distribution.repository)
                instance_ids.append(
                    (distribution.repository.pk, "container", "ContainerPushRepositorySerializer"),
                )

        reservations.append(namespace)
        instance_ids.append(
            (namespace.pk, "container", "ContainerNamespaceSerializer"),
        )
        async_result = enqueue_with_reservation(
            tasks.general_multi_delete, reservations, args=(instance_ids,)
        )
        return OperationPostponedResponse(async_result, request)

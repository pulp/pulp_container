"""
Check `Plugin Writer's Guide`_ for more details.

. _Plugin Writer's Guide:
    http://docs.pulpproject.org/plugins/plugin-writer/index.html
"""
import logging

from django.db import IntegrityError
from django.db.models import Q

from django_filters import CharFilter, MultipleChoiceFilter
from drf_spectacular.utils import extend_schema

from rest_framework import mixins
from rest_framework.decorators import action

from pulpcore.plugin.actions import raise_for_unknown_content_units
from pulpcore.plugin.models import RepositoryVersion
from pulpcore.plugin.serializers import AsyncOperationResponseSerializer
from pulpcore.plugin.models import Artifact, Content
from pulpcore.plugin.tasking import dispatch, general_multi_delete
from pulpcore.plugin.util import get_objects_for_user
from pulpcore.plugin.viewsets import (
    AsyncUpdateMixin,
    DistributionViewSet,
    BaseFilterSet,
    CharInFilter,
    ContentFilter,
    DistributionFilter,
    NamedModelViewSet,
    NAME_FILTER_OPTIONS,
    ReadOnlyContentViewSet,
    ReadOnlyRepositoryViewSet,
    RemoteViewSet,
    RepositoryViewSet,
    RepositoryVersionViewSet,
    RolesMixin,
    OperationPostponedResponse,
)

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

    class Meta:
        model = models.Blob
        fields = {
            "digest": ["exact", "in"],
        }


class ManifestSignatureFilter(ContentFilter):
    """
    FilterSet for image signatures.
    """

    manifest = CharInFilter(field_name="signed_manifest__digest", lookup_expr="in")

    class Meta:
        model = models.ManifestSignature
        fields = {
            "name": NAME_FILTER_OPTIONS,
            "digest": ["exact", "in"],
            "key_id": ["exact", "in"],
        }


class ContainerDistributionFilter(DistributionFilter):
    """
    FilterSet for ContainerDistributions
    """

    namespace__name = CharFilter(lookup_expr="exact")

    class Meta:
        model = models.ContainerDistribution
        fields = DistributionFilter.Meta.fields


class ContainerNamespaceFilter(BaseFilterSet):
    """
    FilterSet for ContainerNamespaces
    """

    class Meta:
        model = models.ContainerNamespace
        fields = {
            "name": NAME_FILTER_OPTIONS,
        }


class ContainerContentQuerySetMixin:
    """
    A mixin that provides container content models with querying utilities.
    """

    def _repo_query_params(self, request, view, push_perm, mirror_perm):
        """
        Checks if the requests' query_params contain repository_version.

        This is used in the quryset scoping for content.

        Args:
            request (rest_framework.request.Request): The request being made.
            view (subclass rest_framework.viewsets.GenericViewSet): The view being checked for
                authorization.
            action (str): The action being performed, e.g. "destroy".
                be checked.

        Returns:
            List of repositories pk that the current user can view

        """
        repo_pks = []
        for key, param in request.query_params.items():
            if "repository_version" in key:
                rv = NamedModelViewSet.get_resource(param, RepositoryVersion)
                repo = rv.repository.cast()
                if isinstance(repo, models.ContainerPushRepository):
                    if request.user.has_perm(push_perm) or any(
                        request.user.has_perm(push_perm, dist.cast())
                        or request.user.has_perm(
                            "container.namespace_view_containerdistribution", dist.cast().namespace
                        )
                        for dist in repo.distributions.all()
                    ):
                        repo_pks.append(repo.pk)
                elif isinstance(repo, models.ContainerRepository):
                    if request.user.has_perm(mirror_perm) or request.user.has_perm(
                        mirror_perm, repo
                    ):
                        repo_pks.append(repo.pk)
        return repo_pks

    def get_content_qs(self, qs, push_perm, mirror_perm):
        """
        Gets a QuerySet based on the current request.

        Filters and retuns the only the repo's content user is allowed to see.

        Returns:
            django.db.models.query.QuerySet: The queryset returned contains content the user is
            allowed to see based on the repo permissions.

        """
        has_model_push_repo = self.request.user.has_perm(push_perm)
        has_model_repo = self.request.user.has_perm(mirror_perm)
        # this will show also orphaned content
        if has_model_push_repo and has_model_repo:
            return qs
        query_params = self.request.query_params
        if query_params and "repository_version" in query_params:
            repo_pks = self._repo_query_params(self.request, self, push_perm, mirror_perm)
            content_qs = qs.model.objects.filter(repositories__in=repo_pks)
        else:
            allowed_push_repos = models.ContainerPushRepository.objects.filter(
                distributions__in=get_objects_for_user(
                    self.request.user,
                    push_perm,
                    models.ContainerDistribution.objects.all(),
                )
            ).only("pk")
            allowed_mirror_repos = get_objects_for_user(
                self.request.user,
                mirror_perm,
                models.ContainerRepository.objects.all(),
            ).only("pk")
            content_qs = qs.model.objects.filter(
                Q(repositories__in=allowed_push_repos) | Q(repositories__in=allowed_mirror_repos)
            )

        return content_qs


class TagViewSet(ContainerContentQuerySetMixin, ReadOnlyContentViewSet):
    """
    ViewSet for Tag.
    """

    endpoint_name = "tags"
    queryset = models.Tag.objects.all()
    serializer_class = serializers.TagSerializer
    filterset_class = TagFilter

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
            },
        ],
        "queryset_scoping": {
            "function": "get_content_qs",
            "parameters": {
                "push_perm": "container.view_containerdistribution",
                "mirror_perm": "container.view_containerrepository",
            },
        },
    }


class ManifestViewSet(ContainerContentQuerySetMixin, ReadOnlyContentViewSet):
    """
    ViewSet for Manifest.
    """

    endpoint_name = "manifests"
    queryset = models.Manifest.objects.all()
    serializer_class = serializers.ManifestSerializer
    filterset_class = ManifestFilter

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
            },
        ],
        "queryset_scoping": {
            "function": "get_content_qs",
            "parameters": {
                "push_perm": "container.view_containerdistribution",
                "mirror_perm": "container.view_containerrepository",
            },
        },
    }


class BlobViewSet(ContainerContentQuerySetMixin, ReadOnlyContentViewSet):
    """
    ViewSet for Blobs.
    """

    endpoint_name = "blobs"
    queryset = models.Blob.objects.all()
    serializer_class = serializers.BlobSerializer
    filterset_class = BlobFilter

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
            },
        ],
        "queryset_scoping": {
            "function": "get_content_qs",
            "parameters": {
                "push_perm": "container.view_containerdistribution",
                "mirror_perm": "container.view_containerrepository",
            },
        },
    }


class ManifestSignatureViewSet(ContainerContentQuerySetMixin, ReadOnlyContentViewSet):
    """
    ViewSet for image signatures.
    """

    endpoint_name = "signatures"
    queryset = models.ManifestSignature.objects.all()
    serializer_class = serializers.ManifestSignatureSerializer
    filterset_class = ManifestSignatureFilter

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
            },
        ],
        "queryset_scoping": {
            "function": "get_content_qs",
            "parameters": {
                "push_perm": "container.view_containerdistribution",
                "mirror_perm": "container.view_containerrepository",
            },
        },
    }


class ContainerRemoteViewSet(RemoteViewSet, RolesMixin):
    """
    Container remotes represent an external repository that implements the Container
    Registry API. Container remotes support deferred downloading by configuring
    the ``policy`` field.  ``on_demand`` and ``streamed`` policies can provide
    significant disk space savings.
    """

    endpoint_name = "container"
    queryset = models.ContainerRemote.objects.all()
    serializer_class = serializers.ContainerRemoteSerializer
    queryset_filtering_required_permission = "container.view_containerremote"

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list", "my_permissions"],
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
                "condition": [
                    "has_model_or_obj_perms:container.change_containerremote",
                    "has_model_or_obj_perms:container.view_containerremote",
                ],
            },
            {
                "action": ["destroy"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_obj_perms:container.delete_containerremote",
                    "has_model_or_obj_perms:container.view_containerremote",
                ],
            },
            {
                "action": ["list_roles", "add_role", "remove_role"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": ["has_model_or_obj_perms:container.manage_roles_containerremote"],
            },
        ],
        "creation_hooks": [
            {
                "function": "add_roles_for_object_creator",
                "parameters": {"roles": "container.containerremote_owner"},
            },
        ],
        "queryset_scoping": {"function": "scope_queryset"},
    }
    LOCKED_ROLES = {
        "container.containerremote_creator": [
            "container.add_containerremote",
        ],
        "container.containerremote_owner": [
            "container.view_containerremote",
            "container.change_containerremote",
            "container.delete_containerremote",
            "container.manage_roles_containerremote",
        ],
        "container.containerremote_viewer": [
            "container.view_containerremote",
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
    )
    @action(detail=True, methods=["post"], serializer_class=serializers.TagImageSerializer)
    def tag(self, request, pk):
        """
        Create a task which is responsible for creating a new tag.
        """
        repository = self.get_object()

        serializer = serializers.TagImageSerializer(
            data=request.data, context={"request": request, "repository": repository}
        )
        serializer.is_valid(raise_exception=True)

        manifest = serializer.validated_data["manifest"]
        tag = serializer.validated_data["tag"]

        result = dispatch(
            tasks.tag_image,
            exclusive_resources=[repository],
            kwargs={
                "manifest_pk": str(manifest.pk),
                "tag": tag,
                "repository_pk": str(repository.pk),
            },
        )
        return OperationPostponedResponse(result, request)

    @extend_schema(
        description="Trigger an asynchronous task to untag an image in the repository",
        summary="Delete a tag",
        responses={202: AsyncOperationResponseSerializer},
    )
    @action(detail=True, methods=["post"], serializer_class=serializers.UnTagImageSerializer)
    def untag(self, request, pk):
        """
        Create a task which is responsible for untagging an image.
        """
        repository = self.get_object()

        serializer = serializers.UnTagImageSerializer(
            data=request.data, context={"request": request, "repository": repository}
        )
        serializer.is_valid(raise_exception=True)

        tag = serializer.validated_data["tag"]

        result = dispatch(
            tasks.untag_image,
            exclusive_resources=[repository],
            kwargs={"tag": tag, "repository_pk": str(repository.pk)},
        )
        return OperationPostponedResponse(result, request)


class SignOperationsMixin:
    """Signing mixing for both types of the repos."""

    @extend_schema(
        description="Trigger an asynchronous task to sign content.",
        summary="Sign images in the repo",
        responses={202: AsyncOperationResponseSerializer},
    )
    @action(detail=True, methods=["post"], serializer_class=serializers.RepositorySignSerializer)
    def sign(self, request, pk):
        """
        Signs manifests by tag in the repository.
        """
        repository = self.get_object()
        serializer = serializers.RepositorySignSerializer(
            data=request.data, context={"request": request, "repository_pk": pk}
        )

        # Validate synchronously to return 400 errors.
        serializer.is_valid(raise_exception=True)
        signing_service = serializer.validated_data.get(
            "manifest_signing_service", repository.manifest_signing_service
        )
        future_base_path = serializer.validated_data.get("future_base_path")
        reference = f"{request.get_host()}/{future_base_path}"

        tags_list = serializer.validated_data.get("tags_list")
        if tags_list:
            tags_list_pks = models.Tag.objects.filter(name__in=tags_list).values_list(
                "pk", flat=True
            )
            tags_list_pks = list(tags_list_pks)
        else:
            tags_list_pks = None
        result = dispatch(
            tasks.sign,
            exclusive_resources=[repository],
            kwargs={
                "repository_pk": repository.pk,
                "reference": reference,
                "signing_service_pk": signing_service.pk,
                "tags_list": tags_list_pks,
            },
        )
        return OperationPostponedResponse(result, request)


class ContainerRepositoryViewSet(
    TagOperationsMixin, SignOperationsMixin, RepositoryViewSet, RolesMixin
):
    """
    ViewSet for container repo.
    """

    endpoint_name = "container"
    queryset = models.ContainerRepository.objects.all()
    serializer_class = serializers.ContainerRepositorySerializer
    queryset_filtering_required_permission = "container.view_containerrepository"
    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list", "my_permissions"],
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
                "condition": [
                    "has_model_or_obj_perms:container.delete_containerrepository",
                    "has_model_or_obj_perms:container.view_containerrepository",
                ],
            },
            {
                "action": ["update", "partial_update"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_obj_perms:container.change_containerrepository",
                    "has_model_or_obj_perms:container.view_containerrepository",
                ],
            },
            {
                "action": ["sync"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_obj_perms:container.sync_containerrepository",
                    "has_remote_param_model_or_obj_perms:container.view_containerremote",
                    "has_model_or_obj_perms:container.view_containerrepository",
                ],
            },
            {
                "action": ["add", "remove", "tag", "untag", "copy_tags", "copy_manifests", "sign"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_obj_perms:container.modify_content_containerrepository",
                    "has_model_or_obj_perms:container.view_containerrepository",
                ],
            },
            {
                "action": ["build_image"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_obj_perms:container.build_image_containerrepository",
                    "has_model_or_obj_perms:container.view_containerrepository",
                ],
            },
            {
                "action": ["list_roles", "add_role", "remove_role"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": ["has_model_or_obj_perms:container.manage_roles_containerrepository"],
            },
        ],
        "creation_hooks": [
            {
                "function": "add_roles_for_object_creator",
                "parameters": {"roles": "container.containerrepository_owner"},
            },
        ],
        "queryset_scoping": {"function": "scope_queryset"},
    }
    LOCKED_ROLES = {
        "container.containerrepository_creator": ["container.add_containerrepository"],
        "container.containerrepository_owner": [
            "container.view_containerrepository",
            "container.change_containerrepository",
            "container.delete_containerrepository",
            "container.delete_containerrepository_versions",
            "container.sync_containerrepository",
            "container.modify_content_containerrepository",
            "container.build_image_containerrepository",
            "container.manage_roles_containerrepository",
        ],
        "container.containerrepository_content_manager": [
            "container.view_containerrepository",
            "container.delete_containerrepository_versions",
            "container.sync_containerrepository",
            "container.modify_content_containerrepository",
            "container.build_image_containerrepository",
        ],
        "container.containerrepository_viewer": [
            "container.view_containerrepository",
        ],
    }

    # This decorator is necessary since a sync operation is asyncrounous and returns
    # the id and href of the sync task.
    @extend_schema(
        description="Trigger an asynchronous task to sync content.",
        summary="Sync from a remote",
        responses={202: AsyncOperationResponseSerializer},
    )
    @action(
        detail=True,
        methods=["post"],
        serializer_class=serializers.ContainerRepositorySyncURLSerializer,
    )
    def sync(self, request, pk):
        """
        Synchronizes a repository. The ``repository`` field has to be provided.
        """
        repository = self.get_object()
        serializer = serializers.ContainerRepositorySyncURLSerializer(
            data=request.data, context={"request": request, "repository_pk": pk}
        )

        # Validate synchronously to return 400 errors.
        serializer.is_valid(raise_exception=True)
        remote = serializer.validated_data.get("remote", repository.remote)
        mirror = serializer.validated_data.get("mirror")
        signed_only = serializer.validated_data.get("signed_only")

        result = dispatch(
            tasks.synchronize,
            shared_resources=[remote],
            exclusive_resources=[repository],
            kwargs={
                "remote_pk": str(remote.pk),
                "repository_pk": str(repository.pk),
                "mirror": mirror,
                "signed_only": signed_only,
            },
        )
        return OperationPostponedResponse(result, request)

    @extend_schema(
        description="Trigger an asynchronous task to recursively add container content.",
        summary="Add content",
        responses={202: AsyncOperationResponseSerializer},
    )
    @action(detail=True, methods=["post"], serializer_class=serializers.RecursiveManageSerializer)
    def add(self, request, pk):
        """
        Queues a task that creates a new RepositoryVersion by adding content units.
        """
        add_content_units = {}
        repository = self.get_object()
        serializer = serializers.RecursiveManageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        if "content_units" in request.data:
            for url in request.data["content_units"]:
                add_content_units[NamedModelViewSet.extract_pk(url)] = url

            self.touch_content_units(add_content_units)

        result = dispatch(
            tasks.recursive_add_content,
            exclusive_resources=[repository],
            kwargs={
                "repository_pk": repository.pk,
                "content_units": list(add_content_units.keys()),
            },
        )
        return OperationPostponedResponse(result, request)

    def touch_content_units(self, content_units):
        """Touch and validate referenced content units."""
        content_units_pks = content_units.keys()
        existing_content_units = Content.objects.filter(pk__in=content_units_pks)
        existing_content_units.touch()

        raise_for_unknown_content_units(existing_content_units, content_units)

    @extend_schema(
        description="Trigger an async task to recursively remove container content.",
        summary="Remove content",
        responses={202: AsyncOperationResponseSerializer},
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
                remove_content_units.append(str(content.pk))

        result = dispatch(
            tasks.recursive_remove_content,
            exclusive_resources=[repository],
            kwargs={"repository_pk": str(repository.pk), "content_units": remove_content_units},
        )
        return OperationPostponedResponse(result, request)

    @extend_schema(
        description="Trigger an asynchronous task to copy tags",
        summary="Copy tags",
        responses={202: AsyncOperationResponseSerializer},
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
        content_tags_in_repo = source_latest.content.filter(pulp_type=models.Tag.get_pulp_type())
        tags_in_repo = models.Tag.objects.filter(pk__in=content_tags_in_repo)
        if names is None:
            tags_to_add = tags_in_repo
        else:
            tags_to_add = tags_in_repo.filter(name__in=names)

        result = dispatch(
            tasks.recursive_add_content,
            shared_resources=[source_latest.repository],
            exclusive_resources=[repository],
            kwargs={
                "repository_pk": str(repository.pk),
                "content_units": [str(pk) for pk in tags_to_add.values_list("pk", flat=True)],
            },
        )
        return OperationPostponedResponse(result, request)

    @extend_schema(
        description="Trigger an asynchronous task to copy manifests",
        summary="Copy manifests",
        responses={202: AsyncOperationResponseSerializer},
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
        content_manifests_in_repo = source_latest.content.filter(
            pulp_type=models.Manifest.get_pulp_type()
        )
        manifests_in_repo = models.Manifest.objects.filter(pk__in=content_manifests_in_repo)
        digests = request.data.get("digests")
        media_types = request.data.get("media_types")
        filters = {}
        if digests is not None:
            filters["digest__in"] = digests
        if media_types is not None:
            filters["media_type__in"] = media_types
        manifests_to_add = manifests_in_repo.filter(**filters)
        result = dispatch(
            tasks.recursive_add_content,
            shared_resources=[source_latest.repository],
            exclusive_resources=[repository],
            kwargs={
                "repository_pk": str(repository.pk),
                "content_units": [str(manifest.pk) for manifest in manifests_to_add],
            },
        )
        return OperationPostponedResponse(result, request)

    @extend_schema(
        description="Trigger an asynchronous task to build an OCI image from a "
        "Containerfile. A new repository version is created with the new "
        "image and tag. This API is tech preview in Pulp Container 1.1. "
        "Backwards compatibility when upgrading is not guaranteed.",
        summary="Build an Image",
        responses={202: AsyncOperationResponseSerializer},
    )
    @action(detail=True, methods=["post"], serializer_class=serializers.OCIBuildImageSerializer)
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
            containerfile.touch()
        tag = serializer.validated_data["tag"]

        artifacts = serializer.validated_data["artifacts"]
        Artifact.objects.filter(pk__in=artifacts.keys()).touch()

        result = dispatch(
            tasks.build_image_from_containerfile,
            exclusive_resources=[repository],
            kwargs={
                "containerfile_pk": str(containerfile.pk),
                "tag": tag,
                "repository_pk": str(repository.pk),
                "artifacts": artifacts,
            },
        )
        return OperationPostponedResponse(result, request)


class ContainerRepositoryVersionViewSet(RepositoryVersionViewSet):
    """
    ContainerRepositoryVersion represents a single container repository version.
    """

    parent_viewset = ContainerRepositoryViewSet

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list", "retrieve"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_repository_model_or_obj_perms:container.view_containerrepository",
            },
            {
                "action": ["destroy"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_repository_model_or_obj_perms:container.delete_containerrepository_versions",  # noqa
                    "has_repository_model_or_obj_perms:container.view_containerrepository",
                ],
            },
            {
                "action": ["destroy"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_repository_model_or_obj_perms:container.delete_containerrepository",
                    "has_repository_model_or_obj_perms:container.view_containerrepository",
                ],
            },
            {
                "action": ["repair"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_repository_model_or_obj_perms:container.sync_containerrepository",
                    "has_repository_model_or_obj_perms:container.view_containerrepository",
                ],
            },
        ],
    }


# Note Push Repositories roles management is deferred to its distributions by default. The
# ``RolesMixin`` is still inherited to allow a custom acces policy to decide differently.
class ContainerPushRepositoryViewSet(
    TagOperationsMixin, SignOperationsMixin, ReadOnlyRepositoryViewSet, AsyncUpdateMixin, RolesMixin
):
    """
    ViewSet for a container push repository.

    POST and DELETE are disallowed because a push repository is tightly coupled with a
    ContainerDistribution which handles it automatically.
    Created - during push operation, removed - with ContainerDistribution removal.
    """

    endpoint_name = "container-push"
    queryset = models.ContainerPushRepository.objects.all()
    serializer_class = serializers.ContainerPushRepositorySerializer

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
                "condition_expression": [
                    "has_namespace_obj_perms:container.namespace_view_containerpush_repository or "
                    "has_distribution_perms:container.view_containerdistribution",
                ],
            },
            {
                "action": ["tag", "untag", "remove_image", "sign", "remove_signatures"],
                "principal": "authenticated",
                "effect": "allow",
                "condition_expression": [
                    "has_namespace_obj_perms:container.namespace_modify_content_containerpushrepository or "  # noqa
                    "has_distribution_perms:container.modify_content_containerpushrepository",
                ],
            },
            {
                "action": ["update", "partial_update"],
                "principal": "authenticated",
                "effect": "allow",
                "condition_expression": [
                    "has_namespace_obj_perms:container.namespace_change_containerpushrepository or "
                    "has_distribution_perms:container.change_containerdistribution",
                ],
            },
        ],
        "queryset_scoping": {
            "function": "get_push_repos_qs",
            "parameters": {
                "ns_perm": "container.view_containernamespace",
                "dist_perm": "container.view_containerdistribution",
            },
        },
    }
    LOCKED_ROLES = {}

    @extend_schema(
        description=(
            "Trigger an asynchronous task to remove a manifest and all its associated "
            "data by a digest"
        ),
        summary="Delete an image from a repository",
        responses={202: AsyncOperationResponseSerializer},
    )
    @action(detail=True, methods=["post"], serializer_class=serializers.RemoveImageSerializer)
    def remove_image(self, request, pk):
        """
        Create a task which deletes an image by the passed digest.
        """
        repository = self.get_object()

        serializer = serializers.RemoveImageSerializer(
            data=request.data, context={"request": request, "repository": repository}
        )
        serializer.is_valid(raise_exception=True)

        content_units_to_remove = list(serializer.validated_data["tags_pks"])
        content_units_to_remove.extend(list(serializer.validated_data["sigs_pks"]))
        content_units_to_remove.append(serializer.validated_data["manifest"].pk)

        result = dispatch(
            tasks.recursive_remove_content,
            exclusive_resources=[repository],
            kwargs={
                "repository_pk": str(repository.pk),
                "content_units": [str(pk) for pk in content_units_to_remove],
            },
        )
        return OperationPostponedResponse(result, request)

    @action(detail=True, methods=["post"], serializer_class=serializers.RemoveSignaturesSerializer)
    def remove_signatures(self, request, pk):
        """
        Create a task which deletes signatures by the passed key_id.
        """
        repository = self.get_object()

        serializer = serializers.RemoveSignaturesSerializer(
            data=request.data, context={"request": request, "repository": repository}
        )
        serializer.is_valid(raise_exception=True)

        content_units_to_remove = list(serializer.validated_data["sigs_pks"])

        result = dispatch(
            tasks.recursive_remove_content,
            exclusive_resources=[repository],
            kwargs={
                "repository_pk": str(repository.pk),
                "content_units": [str(pk) for pk in content_units_to_remove],
            },
        )
        return OperationPostponedResponse(result, request)

    def get_push_repos_qs(self, qs, ns_perm, dist_perm):
        """
        Returns a queryset by filtering by namespace permission to view distributions and
        distribution level permissions.
        """

        qs = models.ContainerPushRepository.objects.all()
        namespaces = get_objects_for_user(
            self.request.user,
            ns_perm,
            models.ContainerNamespace.objects.all(),
        )
        ns_repository_pks = models.ContainerDistribution.objects.filter(
            namespace__in=namespaces
        ).values_list("repository")
        dist_repository_pks = get_objects_for_user(
            self.request.user,
            dist_perm,
            models.ContainerDistribution.objects.all(),
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

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list", "retrieve"],
                "principal": "authenticated",
                "effect": "allow",
                "condition_expression": "has_namespace_obj_perms:container.namespace_view_containerdistribution or "  # noqa
                "has_distribution_perms:container.view_containerdistribution",
            },
        ],
    }


class ContainerDistributionViewSet(DistributionViewSet, RolesMixin):
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

    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list", "my_permissions"],
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
                "condition": "has_namespace_model_perms",
            },
            {
                "action": ["create"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_namespace_perms:container.add_containerdistribution",
            },
            {
                "action": ["create"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "namespace_is_username",
            },
            {
                "action": ["retrieve"],
                "principal": "authenticated",
                "effect": "allow",
                "condition_expression": [
                    "not is_private"
                    " or has_namespace_or_obj_perms:container.view_containerdistribution",
                ],
            },
            {
                "action": ["pull"],
                "principal": "*",
                "effect": "allow",
                "condition_expression": [
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
                    "has_namespace_or_obj_perms:container.change_containerdistribution",
                    "has_namespace_or_obj_perms:container.view_containerdistribution",
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
                    "has_namespace_or_obj_perms:container.view_containerdistribution",
                ],
            },
            {
                "action": ["list_roles", "add_role", "remove_role"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_obj_perms:container.manage_roles_containerdistribution"
                ],
            },
        ],
        "creation_hooks": [
            {
                "function": "add_roles_for_object_creator",
                "parameters": {
                    "roles": "container.containerdistribution_owner",
                },
            },
        ],
        "queryset_scoping": {
            "function": "get_dist_qs",
            "parameters": {
                "ns_perm": "container.view_containernamespace",
                "dist_perm": "container.view_containerdistribution",
            },
        },
    }
    LOCKED_ROLES = {
        "container.containerdistribution_creator": ["container.add_containerdistribution"],
        "container.containerdistribution_owner": [
            "container.view_containerdistribution",
            "container.pull_containerdistribution",
            "container.push_containerdistribution",
            "container.delete_containerdistribution",
            "container.change_containerdistribution",
            "container.manage_roles_containerdistribution",
        ],
        "container.containerdistribution_collaborator": [
            "container.view_containerdistribution",
            "container.pull_containerdistribution",
            "container.push_containerdistribution",
        ],
        "container.containerdistribution_consumer": [
            "container.view_containerdistribution",
            "container.pull_containerdistribution",
        ],
    }

    def get_dist_qs(self, qs, ns_perm, dist_perm):
        """
        Returns a queryset of distributions filtered by namespace permissions and public status.
        """

        public_qs = models.ContainerDistribution.objects.filter(private=False)
        obj_perm_qs = get_objects_for_user(
            self.request.user,
            dist_perm,
            models.ContainerDistribution.objects.all(),
        )
        namespaces = get_objects_for_user(
            self.request.user,
            ns_perm,
            models.ContainerNamespace.objects.all(),
        )
        namespaces |= get_objects_for_user(
            self.request.user,
            dist_perm,
            models.ContainerNamespace.objects.all(),
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
            (str(distribution.pk), "container", "ContainerDistributionSerializer"),
        ]
        if distribution.repository and distribution.repository.cast().PUSH_ENABLED:
            reservations.append(distribution.repository)
            instance_ids.append(
                (str(distribution.repository.pk), "container", "ContainerPushRepositorySerializer"),
            )

        async_result = dispatch(
            general_multi_delete, exclusive_resources=reservations, args=(instance_ids,)
        )
        return OperationPostponedResponse(async_result, request)


class ContainerNamespaceViewSet(
    NamedModelViewSet,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    RolesMixin,
):
    """
    ViewSet for ContainerNamespaces.
    """

    endpoint_name = "pulp_container/namespaces"
    queryset = models.ContainerNamespace.objects.all()
    serializer_class = serializers.ContainerNamespaceSerializer
    filterset_class = ContainerNamespaceFilter
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
                "action": ["create"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "namespace_is_username",
            },
            {
                "action": ["retrieve", "my_permissions"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_or_obj_perms:container.view_containernamespace",
            },
            {
                "action": ["destroy"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": [
                    "has_model_or_obj_perms:container.delete_containernamespace",
                    "has_model_or_obj_perms:container.view_containernamespace",
                ],
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
            {
                "action": ["list_roles", "add_role", "remove_role"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "has_model_or_obj_perms:container.manage_roles_containernamespace",
            },
        ],
        "creation_hooks": [
            {
                "function": "add_roles_for_object_creator",
                "parameters": {
                    "roles": "container.containernamespace_owner",
                },
            }
        ],
        "queryset_scoping": {"function": "scope_queryset"},
    }

    LOCKED_ROLES = {
        "container.containernamespace_creator": [
            "container.add_containernamespace",
        ],
        "container.containernamespace_owner": [
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
            "container.namespace_change_containerpushrepository",
            "container.manage_roles_containernamespace",
        ],
        "container.containernamespace_collaborator": [
            "container.view_containernamespace",
            "container.namespace_add_containerdistribution",
            "container.namespace_delete_containerdistribution",
            "container.namespace_view_containerdistribution",
            "container.namespace_pull_containerdistribution",
            "container.namespace_push_containerdistribution",
            "container.namespace_change_containerdistribution",
            "container.namespace_view_containerpushrepository",
            "container.namespace_modify_content_containerpushrepository",
            "container.namespace_change_containerpushrepository",
        ],
        "container.containernamespace_consumer": [
            "container.view_containernamespace",
            "container.namespace_view_containerdistribution",
            "container.namespace_pull_containerdistribution",
            "container.namespace_view_containerpushrepository",
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
                (str(distribution.pk), "container", "ContainerDistributionSerializer"),
            )
            if distribution.repository and distribution.repository.cast().PUSH_ENABLED:
                reservations.append(distribution.repository)
                instance_ids.append(
                    (
                        str(distribution.repository.pk),
                        "container",
                        "ContainerPushRepositorySerializer",
                    ),
                )

        reservations.append(namespace)
        instance_ids.append(
            (str(namespace.pk), "container", "ContainerNamespaceSerializer"),
        )
        async_result = dispatch(
            general_multi_delete, exclusive_resources=reservations, args=(instance_ids,)
        )
        return OperationPostponedResponse(async_result, request)

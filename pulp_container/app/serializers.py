from gettext import gettext as _
import os

from django.db import IntegrityError
from django.core.exceptions import ObjectDoesNotExist

from rest_framework import serializers

from pulpcore.plugin.models import (
    Artifact,
    Remote,
    RepositoryVersion,
)
from pulpcore.plugin.serializers import (
    ContentGuardSerializer,
    DetailRelatedField,
    IdentityField,
    ModelSerializer,
    NestedRelatedField,
    NoArtifactContentSerializer,
    RelatedField,
    RemoteSerializer,
    RepositorySerializer,
    RepositoryVersionDistributionSerializer,
    SingleArtifactContentSerializer,
    validate_unknown_fields,
)

from . import models

VALID_TAG_REGEX = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"


class _GetOrCreateMixin:
    @classmethod
    def get_or_create(cls, natural_key, default_values=None):
        try:
            result = cls.Meta.model.objects.get(**natural_key)
        except ObjectDoesNotExist:
            data = {}
            if default_values:
                data.update(default_values)
            data.update(natural_key)
            serializer = cls(data=data)
            try:
                serializer.is_valid(raise_exception=True)
                result = serializer.create(serializer.validated_data)
            except (IntegrityError, serializers.ValidationError):
                # recover from a race condition, where another thread just created the object
                result = cls.Meta.model.objects.get(**natural_key)
        return result


class TagSerializer(NoArtifactContentSerializer):
    """
    Serializer for Tags.
    """

    name = serializers.CharField(help_text="Tag name")
    tagged_manifest = DetailRelatedField(
        many=False,
        help_text="Manifest that is tagged",
        view_name="container-manifests-detail",
        queryset=models.Manifest.objects.all(),
    )

    class Meta:
        fields = NoArtifactContentSerializer.Meta.fields + ("name", "tagged_manifest")
        model = models.Tag


class ManifestSerializer(SingleArtifactContentSerializer):
    """
    Serializer for Manifests.
    """

    digest = serializers.CharField(help_text="sha256 of the Manifest file")
    schema_version = serializers.IntegerField(help_text="Manifest schema version")
    media_type = serializers.CharField(help_text="Manifest media type of the file")
    listed_manifests = DetailRelatedField(
        many=True,
        help_text="Manifests that are referenced by this Manifest List",
        view_name="container-manifests-detail",
        queryset=models.Manifest.objects.all(),
    )
    blobs = DetailRelatedField(
        many=True,
        help_text="Blobs that are referenced by this Manifest",
        view_name="container-blobs-detail",
        queryset=models.Blob.objects.all(),
    )
    config_blob = DetailRelatedField(
        many=False,
        required=False,
        help_text="Blob that contains configuration for this Manifest",
        view_name="container-blobs-detail",
        queryset=models.Blob.objects.all(),
    )

    class Meta:
        fields = SingleArtifactContentSerializer.Meta.fields + (
            "digest",
            "schema_version",
            "media_type",
            "listed_manifests",
            "config_blob",
            "blobs",
        )
        model = models.Manifest


class BlobSerializer(SingleArtifactContentSerializer):
    """
    Serializer for Blobs.
    """

    digest = serializers.CharField(help_text="sha256 of the Blob file")
    media_type = serializers.CharField(help_text="Blob media type of the file")

    class Meta:
        fields = SingleArtifactContentSerializer.Meta.fields + ("digest", "media_type")
        model = models.Blob


class RegistryPathField(serializers.CharField):
    """
    Serializer Field for the registry_path field of the ContainerDistribution.
    """

    def to_representation(self, value):
        """
        Converts a base_path into a registry path.
        """
        request = self.context["request"]
        return f"{request.get_host()}/{value}"


class ContainerNamespaceSerializer(ModelSerializer, _GetOrCreateMixin):
    """
    Serializer for ContainerNamespaces.
    """

    pulp_href = IdentityField(view_name="pulp_container/namespaces-detail")

    class Meta:
        fields = ModelSerializer.Meta.fields + ("name",)
        model = models.ContainerNamespace


class ContainerRepositorySerializer(RepositorySerializer):
    """
    Serializer for Container Repositories.
    """

    class Meta:
        fields = RepositorySerializer.Meta.fields
        model = models.ContainerRepository


class ContainerPushRepositorySerializer(RepositorySerializer):
    """
    Serializer for Container Push Repositories.
    """

    class Meta:
        fields = RepositorySerializer.Meta.fields
        model = models.ContainerPushRepository


class ContainerRemoteSerializer(RemoteSerializer):
    """
    A Serializer for ContainerRemote.
    """

    upstream_name = serializers.CharField(
        required=True, allow_blank=False, help_text=_("Name of the upstream repository")
    )
    include_tags = serializers.ListField(
        child=serializers.CharField(max_length=255),
        allow_null=True,
        required=False,
        help_text=_(
            """
            A list of tags to include during sync.
            Wildcards *, ? are recognized.
            'include_tags' is evaluated before 'exclude_tags'.
            """
        ),
    )
    exclude_tags = serializers.ListField(
        child=serializers.CharField(max_length=255),
        allow_null=True,
        required=False,
        help_text=_(
            """
            A list of tags to exclude during sync.
            Wildcards *, ? are recognized.
            'exclude_tags' is evaluated after 'include_tags'.
            """
        ),
    )

    policy = serializers.ChoiceField(
        help_text="""
        immediate - All manifests and blobs are downloaded and saved during a sync.
        on_demand - Only tags and manifests are downloaded. Blobs are not
                    downloaded until they are requested for the first time by a client.
        streamed - Blobs are streamed to the client with every request and never saved.
        """,
        choices=Remote.POLICY_CHOICES,
        default=Remote.IMMEDIATE,
    )

    class Meta:
        fields = RemoteSerializer.Meta.fields + ("upstream_name", "include_tags", "exclude_tags")
        model = models.ContainerRemote


class ContainerDistributionSerializer(RepositoryVersionDistributionSerializer):
    """
    A serializer for ContainerDistribution.
    """

    registry_path = RegistryPathField(
        source="base_path",
        read_only=True,
        help_text=_(
            "The Registry hostame/name/ to use with docker pull command defined by "
            "this distribution."
        ),
    )
    content_guard = DetailRelatedField(
        required=False,
        help_text=_("An optional content-guard. If none is specified, a default one will be used."),
        view_name=r"contentguards-container/content-redirect-detail",
        queryset=models.ContentRedirectContentGuard.objects.all(),
        allow_null=False,
    )
    namespace = RelatedField(
        required=False,
        read_only=True,
        view_name="pulp_container/namespaces-detail",
        help_text=_("Namespace this distribution belongs to."),
    )
    description = serializers.CharField(
        help_text=_("An optional description."), required=False, allow_null=True
    )

    def validate(self, data):
        """
        Validate the ContainterDistribution.

        Make sure there is an instance of ContentRedirectContentGuard always present in validated
        data.
        Validate that the distribution  is not serving a repository versions of a push repository.
        """
        validated_data = super().validate(data)
        if "content_guard" not in validated_data:
            validated_data["content_guard"] = ContentRedirectContentGuardSerializer.get_or_create(
                {"name": "content redirect"}
            )
        if "repository_version" in validated_data:
            repository = validated_data["repository_version"].repository.cast()
            if repository.PUSH_ENABLED:
                raise serializers.ValidationError(
                    _(
                        "A container push repository cannot be distributed by specifying a "
                        "repository version."
                    )
                )

        if "base_path" in validated_data:
            base_path = validated_data["base_path"]
            namespace_name = base_path.split("/")[0]

            if "namespace" in validated_data:
                if validated_data["namespace"].name != namespace_name:
                    raise serializers.ValidationError(
                        _("Selected namespace does not match first component of base_path.")
                    )
            else:
                validated_data["namespace"] = ContainerNamespaceSerializer.get_or_create(
                    {"name": namespace_name}
                )
        return validated_data

    class Meta:
        model = models.ContainerDistribution
        fields = tuple(set(RepositoryVersionDistributionSerializer.Meta.fields) - {"base_url"}) + (
            "registry_path",
            "namespace",
            "private",
            "description",
        )


class ContentRedirectContentGuardSerializer(ContentGuardSerializer, _GetOrCreateMixin):
    """
    A serializer for ContentRedirectContentGuard.
    """

    class Meta(ContentGuardSerializer.Meta):
        model = models.ContentRedirectContentGuard


class TagOperationSerializer(serializers.Serializer):
    """
    A base serializer for tagging and untagging manifests.
    """

    tag = serializers.RegexField(
        regex=VALID_TAG_REGEX,
        required=True,
        help_text="A tag name",
        error_messages={
            "invalid": _(
                "The provided tag is not valid. A tag may contain lowercase and uppercase ASCII "
                "alphabetic characters, digits, underscores, periods, and dashes. A tag must not "
                "start with a period or a dash."
            )
        },
    )

    def validate(self, data):
        """
        Validate data passed through a request call.

        Check if a repository has got a reference to a latest repository version. A
        new dictionary object is initialized by the passed data and altered by a latest
        repository version.
        """
        new_data = {}
        new_data.update(self.initial_data)

        latest_version = new_data["repository"].latest_version()
        if not latest_version:
            raise serializers.ValidationError(
                _(
                    "The latest repository version of '{}' was not found".format(
                        new_data["repository"]
                    )
                )
            )

        new_data["latest_version"] = latest_version
        return new_data


class TagImageSerializer(TagOperationSerializer):
    """
    A serializer for parsing and validating data associated with a manifest tagging.
    """

    digest = serializers.CharField(required=True, help_text="sha256 of the Manifest file")

    def validate(self, data):
        """
        Validate data passed through a request call.

        Manifest with a corresponding digest is retrieved from a database and stored
        in the dictionary to avoid querying the database in the ViewSet again. The
        method checks if the tag exists within the repository.
        """
        new_data = super().validate(data)

        try:
            manifest = models.Manifest.objects.get(
                pk__in=new_data["latest_version"].content.all(), digest=new_data["digest"]
            )
        except models.Manifest.DoesNotExist:
            raise serializers.ValidationError(
                _(
                    "A manifest with the digest '{}' does not "
                    "exist in the latest repository version '{}'".format(
                        new_data["digest"], new_data["latest_version"]
                    )
                )
            )

        new_data["manifest"] = manifest
        return new_data


class UnTagImageSerializer(TagOperationSerializer):
    """
    A serializer for parsing and validating data associated with a manifest untagging.
    """

    def validate(self, data):
        """
        Validate data passed through a request call.

        The method checks if the tag exists within the latest repository version.
        """
        new_data = super().validate(data)

        try:
            models.Tag.objects.get(
                pk__in=new_data["latest_version"].content.all(), name=new_data["tag"]
            )
        except models.Tag.DoesNotExist:
            raise serializers.ValidationError(
                _(
                    "The tag '{}' does not exist in the latest repository version '{}'".format(
                        new_data["tag"], new_data["latest_version"]
                    )
                )
            )

        return new_data


class RecursiveManageSerializer(serializers.Serializer):
    """
    Serializer for adding and removing content to/from a Container repository.
    """

    content_units = serializers.ListField(
        help_text=_("A list of content units to operate on."), required=False
    )

    def validate(self, data):
        """
        Validate data passed through a request call.
        """
        content_units = data.get("content_units", None)
        if content_units:
            if "*" in content_units and len(content_units) > 1:
                raise serializers.ValidationError(
                    _("'*' should be the only item present in the {}".format(content_units))
                )
        return data


class CopySerializer(serializers.Serializer):
    """
    Serializer for copying units from a source repository to a destination repository.
    """

    source_repository = serializers.HyperlinkedRelatedField(
        help_text=_("A URI of the repository to copy content from."),
        queryset=models.ContainerRepository.objects.all(),
        view_name="repositories-container/container-detail",
        label=_("Repository"),
        required=False,
    )
    source_repository_version = NestedRelatedField(
        help_text=_("A URI of the repository version to copy content from."),
        view_name="versions-detail",
        lookup_field="number",
        parent_lookup_kwargs={"repository_pk": "repository__pk"},
        queryset=RepositoryVersion.objects.all(),
        required=False,
    )

    def validate(self, data):
        """Ensure that source_repository or source_rpository_version is pass, but not both."""
        if hasattr(self, "initial_data"):
            validate_unknown_fields(self.initial_data, self.fields)

        repository = data.pop("source_repository", None)
        repository_version = data.get("source_repository_version")
        if not repository and not repository_version:
            raise serializers.ValidationError(
                _("Either the 'repository' or 'repository_version' need to be specified")
            )
        elif not repository and repository_version:
            return data
        elif repository and not repository_version:
            version = repository.latest_version()
            if version:
                new_data = {"source_repository_version": version}
                new_data.update(data)
                return new_data
            else:
                raise serializers.ValidationError(
                    detail=_("Source repository has no version available to copy content from")
                )
        raise serializers.ValidationError(
            _(
                "Either the 'repository' or 'repository_version' need to be specified "
                "but not both."
            )
        )


class TagCopySerializer(CopySerializer):
    """
    Serializer for copying tags from a source repository to a destination repository.
    """

    names = serializers.ListField(
        required=False, allow_null=False, help_text="A list of tag names to copy."
    )


class ManifestCopySerializer(CopySerializer):
    """
    Serializer for copying manifests from a source repository to a destination repository.
    """

    digests = serializers.ListField(
        required=False, allow_null=False, help_text="A list of manifest digests to copy."
    )
    media_types = serializers.MultipleChoiceField(
        choices=models.Manifest.MANIFEST_CHOICES,
        required=False,
        help_text="A list of media_types to copy.",
    )


class RemoveImageSerializer(serializers.Serializer):
    """
    A serializer for parsing and validating data associated with the image removal.
    """

    digest = serializers.CharField(help_text="sha256 of the Manifest file")

    def validate(self, data):
        """
        Validate and extract the latest repository version, manifest, and tags from the passed data.
        """
        new_data = {}
        new_data.update(self.initial_data)

        latest_version = new_data["repository"].latest_version()
        if not latest_version:
            raise serializers.ValidationError(
                _(
                    "The latest repository version of '{}' was not found".format(
                        new_data["repository"]
                    )
                )
            )

        new_data["latest_version"] = latest_version

        try:
            manifest = models.Manifest.objects.get(
                pk__in=new_data["latest_version"].content.all(), digest=new_data["digest"]
            )
        except models.Manifest.DoesNotExist:
            raise serializers.ValidationError(
                _(
                    "A manifest with the digest '{}' does not "
                    "exist in the latest repository version '{}'".format(
                        new_data["digest"], new_data["latest_version"]
                    )
                )
            )

        new_data["manifest"] = manifest

        tags_pks = models.Tag.objects.filter(
            pk__in=new_data["latest_version"].content.all(), tagged_manifest=new_data["manifest"]
        ).values_list("pk", flat=True)
        new_data["tags_pks"] = tags_pks

        return new_data


class OCIBuildImageSerializer(serializers.Serializer):
    """
    Serializer for building an OCI container image from a Containerfile.

    The Containerfile can either be specified via an artifact url, or a new file can be uploaded.
    A repository must be specified, to which the container image content will be added.
    """

    containerfile_artifact = RelatedField(
        many=False,
        lookup_field="pk",
        view_name="artifacts-detail",
        queryset=Artifact.objects.all(),
        help_text=_("Artifact representing the Containerfile that should be used to run buildah."),
    )
    containerfile = serializers.FileField(
        help_text=_("An uploaded Containerfile that should be used to run buildah."),
        required=False,
    )
    tag = serializers.CharField(
        required=False, default="latest", help_text="A tag name for the new image being built."
    )
    artifacts = serializers.JSONField(
        required=False,
        help_text="A JSON string where each key is an artifact href and the value is it's "
        "relative path (name) inside the /pulp_working_directory of the build container "
        "executing the Containerfile.",
    )

    def __init__(self, *args, **kwargs):
        """Initializer for OCIBuildImageSerializer."""
        super().__init__(*args, **kwargs)
        self.fields["containerfile_artifact"].required = False

    def validate(self, data):
        """Validates that all the fields make sense."""
        data = super().validate(data)

        if "containerfile" in data:
            if "containerfile_artifact" in data:
                raise serializers.ValidationError(
                    _("Only one of 'containerfile' and 'containerfile_artifact' may be specified.")
                )
            data["containerfile_artifact"] = Artifact.init_and_validate(data.pop("containerfile"))
        elif "containerfile_artifact" not in data:
            raise serializers.ValidationError(
                _("'containerfile' or 'containerfile_artifact' must " "be specified.")
            )
        artifacts = {}
        if "artifacts" in data:
            for url, relative_path in data["artifacts"].items():
                if os.path.isabs(relative_path):
                    raise serializers.ValidationError(
                        _("Relative path cannot start with '/'. " "{0}").format(relative_path)
                    )
                artifactfield = RelatedField(
                    view_name="artifacts-detail",
                    queryset=Artifact.objects.all(),
                    source="*",
                    initial=url,
                )
                try:
                    artifact = artifactfield.run_validation(data=url)
                    artifacts[artifact.pk] = relative_path
                except serializers.ValidationError as e:
                    # Append the URL of missing Artifact to the error message
                    e.detail[0] = "%s %s" % (e.detail[0], url)
                    raise e
        data["artifacts"] = artifacts
        return data

    class Meta:
        fields = (
            "containerfile_artifact",
            "containerfile",
            "repository",
            "tag",
            "artifacts",
        )

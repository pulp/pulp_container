from gettext import gettext as _

from django.conf import settings

from rest_framework import serializers

from pulpcore.plugin.models import (
    Remote,
    RepositoryVersion,
)
from pulpcore.plugin.serializers import (
    DetailRelatedField,
    NestedRelatedField,
    RemoteSerializer,
    RepositorySerializer,
    RepositoryVersionDistributionSerializer,
    SingleArtifactContentSerializer,
    validate_unknown_fields,
)

from . import models


class TagSerializer(SingleArtifactContentSerializer):
    """
    Serializer for Tags.
    """

    name = serializers.CharField(help_text="Tag name")
    tagged_manifest = DetailRelatedField(
        many=False,
        help_text="Manifest that is tagged",
        view_name='container-manifests-detail',
        queryset=models.Manifest.objects.all()
    )

    class Meta:
        fields = SingleArtifactContentSerializer.Meta.fields + (
            'name',
            'tagged_manifest',
        )
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
        view_name='container-manifests-detail',
        queryset=models.Manifest.objects.all()
    )
    blobs = DetailRelatedField(
        many=True,
        help_text="Blobs that are referenced by this Manifest",
        view_name='container-blobs-detail',
        queryset=models.Blob.objects.all()
    )
    config_blob = DetailRelatedField(
        many=False,
        help_text="Blob that contains configuration for this Manifest",
        view_name='container-blobs-detail',
        queryset=models.Blob.objects.all()
    )

    class Meta:
        fields = SingleArtifactContentSerializer.Meta.fields + (
            'digest',
            'schema_version',
            'media_type',
            'listed_manifests',
            'config_blob',
            'blobs',
        )
        model = models.Manifest


class BlobSerializer(SingleArtifactContentSerializer):
    """
    Serializer for Blobs.
    """

    digest = serializers.CharField(help_text="sha256 of the Blob file")
    media_type = serializers.CharField(help_text="Blob media type of the file")

    class Meta:
        fields = SingleArtifactContentSerializer.Meta.fields + (
            'digest',
            'media_type',
        )
        model = models.Blob


class RegistryPathField(serializers.CharField):
    """
    Serializer Field for the registry_path field of the ContainerDistribution.
    """

    def to_representation(self, value):
        """
        Converts a base_path into a registry path.
        """
        host = settings.CONTENT_ORIGIN
        return ''.join([host.split('//')[-1], '/', value])


class ContainerRepositorySerializer(RepositorySerializer):
    """
    Serializer for Container Repositories.
    """

    class Meta:
        fields = RepositorySerializer.Meta.fields
        model = models.ContainerRepository


class ContainerRemoteSerializer(RemoteSerializer):
    """
    A Serializer for ContainerRemote.
    """

    upstream_name = serializers.CharField(
        required=True,
        allow_blank=False,
        help_text=_("Name of the upstream repository")
    )
    whitelist_tags = serializers.ListField(
        child=serializers.CharField(max_length=255),
        allow_null=True,
        required=False,
        help_text=_("A list of whitelisted tags to sync")
    )

    policy = serializers.ChoiceField(
        help_text="""
        immediate - All manifests and blobs are downloaded and saved during a sync.
        on_demand - Only tags and manifests are downloaded. Blobs are not
                    downloaded until they are requested for the first time by a client.
        streamed - Blobs are streamed to the client with every request and never saved.
        """,
        choices=Remote.POLICY_CHOICES,
        default=Remote.IMMEDIATE
    )

    class Meta:
        fields = RemoteSerializer.Meta.fields + ('upstream_name', 'whitelist_tags',)
        model = models.ContainerRemote


class ContainerDistributionSerializer(RepositoryVersionDistributionSerializer):
    """
    A serializer for ContainerDistribution.
    """

    registry_path = RegistryPathField(
        source='base_path', read_only=True,
        help_text=_('The Registry hostame:port/name/ to use with docker pull command defined by '
                    'this distribution.')
    )

    class Meta:
        model = models.ContainerDistribution
        fields = tuple(set(RepositoryVersionDistributionSerializer.Meta.fields) - {'base_url'}) + (
            'registry_path',)


class TagOperationSerializer(serializers.Serializer):
    """
    A base serializer for tagging and untagging manifests.
    """

    tag = serializers.CharField(
        required=True,
        help_text='A tag name'
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

        latest_version = new_data['repository'].latest_version()
        if not latest_version:
            raise serializers.ValidationError(
                _("The latest repository version of '{}' was not found"
                  .format(data['repository']))
            )

        new_data['latest_version'] = latest_version
        return new_data


class TagImageSerializer(TagOperationSerializer):
    """
    A serializer for parsing and validating data associated with a manifest tagging.
    """

    digest = serializers.CharField(
        required=True,
        help_text='sha256 of the Manifest file'
    )

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
                pk__in=new_data['latest_version'].content.all(),
                digest=new_data['digest']
            )
        except models.Manifest.DoesNotExist:
            raise serializers.ValidationError(
                _("A manifest with the digest '{}' does not "
                  "exist in the latest repository version '{}'"
                  .format(new_data['digest'], new_data['latest_version']))
            )

        new_data['manifest'] = manifest
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
                pk__in=new_data['latest_version'].content.all(),
                name=new_data['tag']
            )
        except models.Tag.DoesNotExist:
            raise serializers.ValidationError(
                _("The tag '{}' does not exist in the latest repository version '{}'"
                  .format(new_data['tag'], new_data['latest_version']))
            )

        return new_data


class RecursiveManageSerializer(serializers.Serializer):
    """
    Serializer for adding and removing content to/from a Container repository.
    """

    content_units = serializers.ListField(
        help_text=_('A list of content units to operate on.'),
        write_only=True,
        required=False
    )


class CopySerializer(serializers.Serializer):
    """
    Serializer for copying units from a source repository to a destination repository.
    """

    source_repository = serializers.HyperlinkedRelatedField(
        help_text=_('A URI of the repository to copy content from.'),
        queryset=models.ContainerRepository.objects.all(),
        view_name='repositories-container/container-detail',
        label=_('Repository'),
        write_only=True,
        required=False,
    )
    source_repository_version = NestedRelatedField(
        help_text=_('A URI of the repository version to copy content from.'),
        view_name='versions-detail',
        lookup_field='number',
        parent_lookup_kwargs={'repository_pk': 'repository__pk'},
        queryset=RepositoryVersion.objects.all(),
        write_only=True,
        required=False,
    )

    def validate(self, data):
        """Ensure that source_repository or source_rpository_version is pass, but not both."""
        if hasattr(self, 'initial_data'):
            validate_unknown_fields(self.initial_data, self.fields)

        repository = data.pop('source_repository', None)
        repository_version = data.get('source_repository_version')
        if not repository and not repository_version:
            raise serializers.ValidationError(
                _("Either the 'repository' or 'repository_version' need to be specified"))
        elif not repository and repository_version:
            return data
        elif repository and not repository_version:
            version = repository.latest_version()
            if version:
                new_data = {'source_repository_version': version}
                new_data.update(data)
                return new_data
            else:
                raise serializers.ValidationError(
                    detail=_('Source repository has no version available to copy content from'))
        raise serializers.ValidationError(
            _("Either the 'repository' or 'repository_version' need to be specified "
              "but not both.")
        )


class TagCopySerializer(CopySerializer):
    """
    Serializer for copying tags from a source repository to a destination repository.
    """

    names = serializers.ListField(
        required=False,
        allow_null=False,
        help_text="A list of tag names to copy."
    )


class ManifestCopySerializer(CopySerializer):
    """
    Serializer for copying manifests from a source repository to a destination repository.
    """

    digests = serializers.ListField(
        required=False,
        allow_null=False,
        help_text="A list of manifest digests to copy."
    )
    media_types = serializers.MultipleChoiceField(
        choices=models.Manifest.MANIFEST_CHOICES,
        required=False,
        help_text="A list of media_types to copy."
    )

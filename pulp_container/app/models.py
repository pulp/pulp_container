import re

from logging import getLogger

from django.db import models
from django.contrib.postgres import fields

from pulpcore.plugin.download import DownloaderFactory
from pulpcore.plugin.models import (
    Content,
    Remote,
    Repository,
    RepositoryVersionDistribution
)
from pulpcore.plugin.repo_version_utils import remove_duplicates, validate_repo_version

from . import downloaders
from pulp_container.constants import MEDIA_TYPE


logger = getLogger(__name__)


class Blob(Content):
    """
    A blob defined within a manifest.

    The actual blob file is stored as an artifact.

    Fields:
        digest (models.CharField): The blob digest.
        media_type (models.CharField): The blob media type.

    Relations:
        manifest (models.ForeignKey): Many-to-one relationship with Manifest.
    """

    TYPE = 'blob'

    BLOB_CHOICES = (
        (MEDIA_TYPE.CONFIG_BLOB, MEDIA_TYPE.CONFIG_BLOB),
        (MEDIA_TYPE.REGULAR_BLOB, MEDIA_TYPE.REGULAR_BLOB),
        (MEDIA_TYPE.FOREIGN_BLOB, MEDIA_TYPE.FOREIGN_BLOB),
        (MEDIA_TYPE.CONFIG_BLOB_OCI, MEDIA_TYPE.CONFIG_BLOB_OCI),
        (MEDIA_TYPE.REGULAR_BLOB_OCI, MEDIA_TYPE.REGULAR_BLOB_OCI),
        (MEDIA_TYPE.FOREIGN_BLOB_OCI, MEDIA_TYPE.FOREIGN_BLOB_OCI),
    )
    digest = models.CharField(max_length=255, db_index=True)
    media_type = models.CharField(
        max_length=80,
        choices=BLOB_CHOICES
    )

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = ('digest',)


class Manifest(Content):
    """
    A container manifest.

    This content has one artifact.

    Fields:
        digest (models.CharField): The manifest digest.
        schema_version (models.IntegerField): The manifest schema version.
        media_type (models.CharField): The manifest media type.

    Relations:
        blobs (models.ManyToManyField): Many-to-many relationship with Blob.
        config_blob (models.ForeignKey): Blob that contains configuration for this Manifest.
        listed_manifests (models.ManyToManyField): Many-to-many relationship with Manifest. This
            field is used only for a manifest-list type Manifests.
    """

    TYPE = 'manifest'

    MANIFEST_CHOICES = (
        (MEDIA_TYPE.MANIFEST_V1, MEDIA_TYPE.MANIFEST_V1),
        (MEDIA_TYPE.MANIFEST_V2, MEDIA_TYPE.MANIFEST_V2),
        (MEDIA_TYPE.MANIFEST_LIST, MEDIA_TYPE.MANIFEST_LIST),
        (MEDIA_TYPE.MANIFEST_OCI, MEDIA_TYPE.MANIFEST_OCI),
        (MEDIA_TYPE.INDEX_OCI, MEDIA_TYPE.INDEX_OCI),
    )
    digest = models.CharField(max_length=255, db_index=True)
    schema_version = models.IntegerField()
    media_type = models.CharField(
        max_length=60,
        choices=MANIFEST_CHOICES)

    blobs = models.ManyToManyField(Blob, through='BlobManifest')
    config_blob = models.ForeignKey(Blob, related_name='config_blob',
                                    null=True, on_delete=models.CASCADE)

    # Order matters for through fields, (source, target)
    listed_manifests = models.ManyToManyField(
        "self",
        through='ManifestListManifest',
        symmetrical=False,
        through_fields=('image_manifest', 'manifest_list')
    )

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = ('digest',)


class BlobManifest(models.Model):
    """
    Many-to-many relationship between Blobs and Manifests.
    """

    manifest = models.ForeignKey(
        Manifest, related_name='blob_manifests', on_delete=models.CASCADE)
    manifest_blob = models.ForeignKey(
        Blob, related_name='manifest_blobs', on_delete=models.CASCADE)

    class Meta:
        unique_together = ('manifest', 'manifest_blob')


class ManifestListManifest(models.Model):
    """
    The manifest referenced by a manifest list.

    Fields:
        architecture (models.CharField): The platform architecture.
        variant (models.CharField): The platform variant.
        features (models.TextField): The platform features.
        os (models.CharField): The platform OS name.
        os_version (models.CharField): The platform OS version.
        os_features (models.TextField): The platform OS features.

    Relations:
        manifest (models.ForeignKey): Many-to-one relationship with Manifest.
        manifest_list (models.ForeignKey): Many-to-one relationship with ManifestList.
    """

    architecture = models.CharField(max_length=255)
    os = models.CharField(max_length=255)
    os_version = models.CharField(max_length=255, default='', blank=True)
    os_features = models.TextField(default='', blank=True)
    features = models.TextField(default='', blank=True)
    variant = models.CharField(max_length=255, default='', blank=True)

    image_manifest = models.ForeignKey(
        Manifest, related_name='image_manifests', on_delete=models.CASCADE)
    manifest_list = models.ForeignKey(
        Manifest, related_name='manifest_lists', on_delete=models.CASCADE)

    class Meta:
        unique_together = ('image_manifest', 'manifest_list')


class Tag(Content):
    """
    A tagged Manifest.

    Fields:
        name (models.CharField): The tag name.

    Relations:
        tagged_manifest (models.ForeignKey): A referenced Manifest.

    """

    TYPE = 'tag'
    repo_key_fields = ('name',)

    name = models.CharField(max_length=255, db_index=True)

    tagged_manifest = models.ForeignKey(
        Manifest, null=True, related_name='tagged_manifests', on_delete=models.CASCADE)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = (
            ('name', 'tagged_manifest'),
        )


class ContainerRepository(Repository):
    """
    Repository for "container" content.
    """

    TYPE = "container"
    CONTENT_TYPES = [Blob, Manifest, Tag]

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"

    def finalize_new_version(self, new_version):
        """
        Ensure no added content Tags contain the same `name`.
        Args:
            new_version (pulpcore.app.models.RepositoryVersion): The incomplete RepositoryVersion to
                finalize.
        """
        remove_duplicates(new_version)
        validate_repo_version(new_version)


class ContainerRemote(Remote):
    """
    A Remote for ContainerContent.

    Fields:
        upstream_name (models.CharField): The name of the image at the remote.
        include_foreign_layers (models.BooleanField): Foreign layers in the remote
            are included. They are not included by default.
    """

    upstream_name = models.CharField(max_length=255, db_index=True)
    include_foreign_layers = models.BooleanField(default=False)
    whitelist_tags = fields.ArrayField(
        models.CharField(max_length=255, null=True),
        null=True
    )

    TYPE = 'container'

    @property
    def download_factory(self):
        """
        Return the DownloaderFactory which can be used to generate asyncio capable downloaders.

        Upon first access, the DownloaderFactory is instantiated and saved internally.

        Plugin writers are expected to override when additional configuration of the
        DownloaderFactory is needed.

        Returns:
            DownloadFactory: The instantiated DownloaderFactory to be used by
                get_downloader()

        """
        try:
            return self._download_factory
        except AttributeError:
            self._download_factory = DownloaderFactory(
                self,
                downloader_overrides={
                    'http': downloaders.RegistryAuthHttpDownloader,
                    'https': downloaders.RegistryAuthHttpDownloader,
                }
            )
            return self._download_factory

    def get_downloader(self, remote_artifact=None, url=None, **kwargs):
        """
        Get a downloader from either a RemoteArtifact or URL that is configured with this Remote.

        This method accepts either `remote_artifact` or `url` but not both. At least one is
        required. If neither or both are passed a ValueError is raised.

        Args:
            remote_artifact (:class:`~pulpcore.app.models.RemoteArtifact`): The RemoteArtifact to
                download.
            url (str): The URL to download.
            kwargs (dict): This accepts the parameters of
                :class:`~pulpcore.plugin.download.BaseDownloader`.

        Raises:
            ValueError: If neither remote_artifact and url are passed, or if both are passed.

        Returns:
            subclass of :class:`~pulpcore.plugin.download.BaseDownloader`: A downloader that
            is configured with the remote settings.

        """
        kwargs['remote'] = self
        return super().get_downloader(remote_artifact=remote_artifact, url=url, **kwargs)

    @property
    def namespaced_upstream_name(self):
        """
        Returns an upstream Container repository name with a namespace.

        For upstream repositories that do not have a namespace, the convention is to use 'library'
        as the namespace.
        """
        # Docker's registry aligns non-namespaced images to the library namespace.
        container_registry = re.search(r'registry[-,\w]*.docker.io', self.url, re.IGNORECASE)
        if '/' not in self.upstream_name and container_registry:
            return 'library/{name}'.format(name=self.upstream_name)
        else:
            return self.upstream_name

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"


class ContainerDistribution(RepositoryVersionDistribution):
    """
    A container distribution defines how a publication is distributed by Pulp's webserver.
    """

    TYPE = 'container'

    def get_repository_version(self):
        """
        Returns the repository version that is supposed to be served by this ContainerDistribution.
        """
        if self.repository:
            return self.repository.latest_version()
        elif self.repository_version:
            return self.repository_version
        else:
            return None

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"

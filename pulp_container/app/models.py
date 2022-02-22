from gettext import gettext as _

import gnupg
import json
import os
import re
import tempfile
import time
from logging import getLogger

from django.db import models
from django.contrib.postgres import fields
from django.shortcuts import redirect

from django_currentuser.middleware import get_current_authenticated_user
from django_lifecycle import hook

from guardian.models.models import GroupObjectPermission, UserObjectPermission
from guardian.shortcuts import assign_perm

from pulpcore.plugin.download import DownloaderFactory
from pulpcore.plugin.models import (
    AutoAddObjPermsMixin,
    AutoDeleteObjPermsMixin,
    BaseModel,
    Content,
    Group,
    Remote,
    Repository,
    Distribution,
    SigningService,
    Upload as CoreUpload,
)
from pulpcore.plugin.repo_version_utils import remove_duplicates, validate_repo_version


from . import downloaders
from pulp_container.constants import MEDIA_TYPE, SIGNATURE_TYPE


gpg = gnupg.GPG()
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

    PROTECTED_FROM_RECLAIM = False

    TYPE = "blob"

    digest = models.CharField(max_length=255, db_index=True)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = ("digest",)


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

    PROTECTED_FROM_RECLAIM = False

    TYPE = "manifest"

    MANIFEST_CHOICES = (
        (MEDIA_TYPE.MANIFEST_V1, MEDIA_TYPE.MANIFEST_V1),
        (MEDIA_TYPE.MANIFEST_V2, MEDIA_TYPE.MANIFEST_V2),
        (MEDIA_TYPE.MANIFEST_LIST, MEDIA_TYPE.MANIFEST_LIST),
        (MEDIA_TYPE.MANIFEST_OCI, MEDIA_TYPE.MANIFEST_OCI),
        (MEDIA_TYPE.INDEX_OCI, MEDIA_TYPE.INDEX_OCI),
    )
    digest = models.CharField(max_length=255, db_index=True)
    schema_version = models.IntegerField()
    media_type = models.CharField(max_length=60, choices=MANIFEST_CHOICES)

    blobs = models.ManyToManyField(Blob, through="BlobManifest")
    config_blob = models.ForeignKey(
        Blob, related_name="config_blob", null=True, on_delete=models.CASCADE
    )

    # Order matters for through fields, (source, target)
    listed_manifests = models.ManyToManyField(
        "self",
        through="ManifestListManifest",
        symmetrical=False,
        through_fields=("image_manifest", "manifest_list"),
    )

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = ("digest",)


class BlobManifest(models.Model):
    """
    Many-to-many relationship between Blobs and Manifests.
    """

    manifest = models.ForeignKey(Manifest, related_name="blob_manifests", on_delete=models.CASCADE)
    manifest_blob = models.ForeignKey(Blob, related_name="manifest_blobs", on_delete=models.CASCADE)

    class Meta:
        unique_together = ("manifest", "manifest_blob")


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
    os_version = models.CharField(max_length=255, default="", blank=True)
    os_features = models.TextField(default="", blank=True)
    features = models.TextField(default="", blank=True)
    variant = models.CharField(max_length=255, default="", blank=True)

    image_manifest = models.ForeignKey(
        Manifest, related_name="image_manifests", on_delete=models.CASCADE
    )
    manifest_list = models.ForeignKey(
        Manifest, related_name="manifest_lists", on_delete=models.CASCADE
    )

    class Meta:
        unique_together = ("image_manifest", "manifest_list")


class Tag(Content):
    """
    A tagged Manifest.

    Fields:
        name (models.CharField): The tag name.

    Relations:
        tagged_manifest (models.ForeignKey): A referenced Manifest.

    """

    TYPE = "tag"
    repo_key_fields = ("name",)

    name = models.CharField(max_length=255, db_index=True)

    # TODO This should be 'null=False'.
    tagged_manifest = models.ForeignKey(
        Manifest, null=True, related_name="tagged_manifests", on_delete=models.CASCADE
    )

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = (("name", "tagged_manifest"),)


class ManifestSignature(Content):
    """
    A signature for a manifest.

    Fields:
        name (models.CharField): A signature name in the 'manifest_digest@random_name' format.
        digest (models.CharField): A signature sha256 digest prepended with its algorithm `sha256:`.
        type (models.CharField): A signature type as specified in signature metadata. Currently
                                 it's only "atomic container signature".
        key_id (models.CharField): A key id identified by gpg (last 8 bytes of the fingerprint).
        timestamp (models.PositiveIntegerField): A signature timestamp identified by gpg.
        creator (models.CharField): A signature creator.
        data (models.TextField): A signature, base64 encoded.

    Relations:
        signed_manifest (models.ForeignKey): A manifest this signature is relevant to.

    """

    PROTECTED_FROM_RECLAIM = False

    TYPE = "signature"

    SIGNATURE_CHOICES = ((SIGNATURE_TYPE.ATOMIC_SHORT, SIGNATURE_TYPE.ATOMIC_SHORT),)

    name = models.CharField(max_length=255, db_index=True)
    digest = models.CharField(max_length=255)
    type = models.CharField(max_length=255, choices=SIGNATURE_CHOICES)
    key_id = models.CharField(max_length=255, db_index=True)
    timestamp = models.PositiveIntegerField()
    creator = models.CharField(max_length=255, blank=True)
    data = models.TextField()

    signed_manifest = models.ForeignKey(
        Manifest, null=False, related_name="signed_manifests", on_delete=models.CASCADE
    )
    # TODO: Maybe there should be an optional field with a FK to a signing_service for the cases
    #       when Pulp creates a signature.

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = (("digest",),)


class ContainerNamespace(BaseModel, AutoAddObjPermsMixin):
    """
    Namespace for the container registry.

    Fields:
        name (models.CharField): The name of the namespace.
    """

    name = models.CharField(max_length=255, db_index=True)

    def create_namespace_group(self, permissions, parameters):
        """
        Creates a namespace group and optionally adds the current user to it.

        The parameters are specified as a dictionary with the following keys:

        "group_type" - the type of group - owners, collaborators, or consumers
        "add_user_to_group" - a boolean that specifies if the current user should be added to the
                              group.

        The permissions are object level permissions assigned to the group.
        """

        group_type = parameters["group_type"]
        add_user_to_group = parameters["add_user_to_group"]
        group = Group.objects.create(
            name="{}.{}.{}".format("container.namespace", group_type, self.name)
        )
        current_user = get_current_authenticated_user()
        owners_group = Group.objects.get(
            name="{}.{}".format("container.namespace.owners", self.name)
        )
        assign_perm("core.change_group", owners_group, group)
        assign_perm("core.view_group", owners_group, group)
        if add_user_to_group:
            current_user.groups.add(group)
        self.add_for_groups(permissions, group.name)

    @hook("before_delete")
    def delete_groups_and_user_obj_perms(self):
        """
        Delete all auto created groups associated with this Namespace and user object
        permissions.
        """
        group_name_regex = r"container.namespace.(.*).{}".format(self.name)
        Group.objects.filter(name__regex=group_name_regex).delete()
        UserObjectPermission.objects.filter(object_pk=self.pk).delete()
        GroupObjectPermission.objects.filter(object_pk=self.pk).delete()

    class Meta:
        unique_together = (("name",),)
        permissions = [
            ("namespace_add_containerdistribution", "Add any distribution to a namespace"),
            ("namespace_delete_containerdistribution", "Delete any distribution from a namespace"),
            ("namespace_view_containerdistribution", "View any distribution in a namespace"),
            ("namespace_pull_containerdistribution", "Pull from any distribution in a namespace"),
            ("namespace_push_containerdistribution", "Push to any distribution in a namespace"),
            ("namespace_change_containerdistribution", "Change any distribution in a namespace"),
            ("namespace_view_containerpushrepository", "View any push repository in a namespace"),
            (
                "namespace_modify_content_containerpushrepository",
                "Modify content in any push repository in a namespace",
            ),
            (
                "namespace_change_containerpushrepository",
                "Update any existing push repository in a namespace",
            ),
            (
                "manage_roles_containernamespace",
                "Can manage role assignments on container namespace",
            ),
        ]


class ContainerRemote(Remote, AutoAddObjPermsMixin, AutoDeleteObjPermsMixin):
    """
    A Remote for ContainerContent.

    Fields:
        upstream_name (models.CharField): The name of the image at the remote.
        include_foreign_layers (models.BooleanField): Foreign layers in the remote
            are included. They are not included by default.
        include_tags (fields.ArrayField): List of tags to include during sync.
        exclude_tags (fields.ArrayField): List of tags to exclude during sync.
        sigstore (models.TextField): The URL to a sigstore where signatures of container images
            should be synced from.
    """

    upstream_name = models.CharField(max_length=255, db_index=True)
    include_foreign_layers = models.BooleanField(default=False)
    include_tags = fields.ArrayField(models.CharField(max_length=255, null=True), null=True)
    exclude_tags = fields.ArrayField(models.CharField(max_length=255, null=True), null=True)
    sigstore = models.TextField(null=True)

    TYPE = "container"

    @property
    def download_factory(self):
        """
        Downloader Factory that maps to custom downloaders which support registry auth.

        Upon first access, the DownloaderFactory is instantiated and saved internally.

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
                    "http": downloaders.RegistryAuthHttpDownloader,
                    "https": downloaders.RegistryAuthHttpDownloader,
                },
            )
            return self._download_factory

    @property
    def noauth_download_factory(self):
        """
        Downloader Factory that doesn't use Basic Auth or TLS settings from a remote.

        Some supplementary data, e.g. signatures, might be available via unprotected resources.

        Upon first access, the NoAuthDownloaderFactory is instantiated and saved internally.

        Returns:
            DownloadFactory: The instantiated NoAuthDownloaderFactory to be used by
                get_noauth_downloader().

        """
        try:
            return self._noauth_download_factory
        except AttributeError:
            self._noauth_download_factory = downloaders.NoAuthDownloaderFactory(self)
            return self._noauth_download_factory

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
        kwargs["remote"] = self
        return super().get_downloader(remote_artifact=remote_artifact, url=url, **kwargs)

    def get_noauth_downloader(self, remote_artifact=None, url=None, **kwargs):
        """
        Get a no-auth downloader from either a RemoteArtifact or URL that is provided.

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
        return super().get_downloader(
            remote_artifact=remote_artifact,
            url=url,
            download_factory=self.noauth_download_factory,
            **kwargs,
        )

    @property
    def namespaced_upstream_name(self):
        """
        Returns an upstream Container repository name with a namespace.

        For upstream repositories that do not have a namespace, the convention is to use 'library'
        as the namespace.
        """
        # Docker's registry aligns non-namespaced images to the library namespace.
        container_registry = re.search(r"registry[-,\w]*.docker.io", self.url, re.IGNORECASE)
        if "/" not in self.upstream_name and container_registry:
            return "library/{name}".format(name=self.upstream_name)
        else:
            return self.upstream_name

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        permissions = [
            (
                "manage_roles_containerremote",
                "Can manage role assignments on container remote",
            ),
        ]


class ManifestSigningService(SigningService):
    """
    Signing service used for creating container signatures.
    """

    def validate(self):
        """
        Validate a signing service for a container signature.

        The validation seeks to ensure that the sign() method returns a dict as follows:

        {"signature": "$SIG_PATH"}

        The method creates a test image manifest, signs its manifest.json, and checks if the
        signature can be verified by the provided public key.

        Raises:
            RuntimeError: If the validation has failed.

        """
        test_manifest = {
            "schemaVersion": 2,
            "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
            "config": {
                "mediaType": "application/vnd.docker.container.image.v1+json",
                "size": 1456,
                "digest": "sha256:7138284460ffa3bb6ee087344f5b051468b3f8697e2d1427bac1a208d4168123",
            },
            "layers": [
                {
                    "mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip",
                    "size": 772792,
                    "digest": "sha256:e685c5c858e36338a47c627763b50dfe6035b547f1f75f0d39753d4e3121",
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_directory_name:
            manifest_file = tempfile.NamedTemporaryFile(dir=temp_directory_name, delete=False)
            with open(manifest_file.name, "w") as outfile:
                json.dump(test_manifest, outfile)
            sig_path = os.path.join(temp_directory_name, "signature")

            signed = self.sign(
                manifest_file.name, env_vars={"REFERENCE": "test", "SIG_PATH": sig_path}
            )

            with open(signed["signature_path"], "rb") as fp:
                verified = gpg.verify_file(fp)
                if verified.trust_level is None or verified.trust_level < verified.TRUST_FULLY:
                    raise RuntimeError(
                        _(
                            "The signature could not be verified or the trust level is too "
                            "low. The signing script may generate invalid signatures."
                        )
                    )
                elif verified.pubkey_fingerprint != self.pubkey_fingerprint:
                    raise RuntimeError(
                        _(
                            "Fingerprints of the provided public key and the verified public "
                            "key are not equal. The signing script is probably not valid."
                        )
                    )


class ContainerRepository(
    Repository,
    AutoAddObjPermsMixin,
    AutoDeleteObjPermsMixin,
):
    """
    Repository for "container" content.

    This Repository type is designed for standard pulp operations, and can be distributed as a
    read only registry.

    Relations:
        manifest_signing_service (models.ForeignKey): ManifestSigningService this repository will
                                                      use for signing content.
    """

    TYPE = "container"
    CONTENT_TYPES = [Blob, Manifest, Tag, ManifestSignature]
    REMOTE_TYPES = [ContainerRemote]
    PUSH_ENABLED = False

    manifest_signing_service = models.ForeignKey(
        ManifestSigningService, on_delete=models.SET_NULL, null=True
    )

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        permissions = [
            ("sync_containerrepository", "Can start a sync task"),
            ("modify_content_containerrepository", "Can modify content in a repository"),
            ("build_image_containerrepository", "Can use the image builder in a repository"),
            ("delete_containerrepository_versions", "Can delete repository versions"),
            (
                "manage_roles_containerrepository",
                "Can manage role assignments on container repository",
            ),
        ]

    def finalize_new_version(self, new_version):
        """
        Ensure no added content Tags contain the same `name`.
        Args:
            new_version (pulpcore.app.models.RepositoryVersion): The incomplete RepositoryVersion to
                finalize.
        """
        remove_duplicates(new_version)
        validate_repo_version(new_version)


class ContainerPushRepository(Repository, AutoAddObjPermsMixin, AutoDeleteObjPermsMixin):
    """
    Repository for "container" content.

    This repository type is designed for the read and write registry usecase. It will be
    automatically instantiated on authorised push to nonexisting repositories.
    With this repository type, all but the latest repository_version are solely of historical
    interest.

    Relations:
        manifest_signing_service (models.ForeignKey): ManifestSigningService this repository will
                                                      use for signing content.
    """

    TYPE = "container-push"
    CONTENT_TYPES = [Blob, Manifest, Tag, ManifestSignature]
    PUSH_ENABLED = True

    manifest_signing_service = models.ForeignKey(
        ManifestSigningService, on_delete=models.SET_NULL, null=True
    )

    def add_perms_to_distribution_group(self, permissions, parameters):
        """
        Adds push repository object permissions to a distribution group.

        The parameters are specified as a dictionary with the following keys:

        "group_type" - the type of group - owners, collaborators, or consumers
        "add_user_to_group" - a boolean that specifies if the current user should be added to the
                              group.

        The permissions are object level permissions assigned to the group.
        """

        group_type = parameters["group_type"]
        add_user_to_group = parameters["add_user_to_group"]
        try:
            suffix = ContainerDistribution.objects.get(repository=self).pk
        except ContainerDistribution.DoesNotExist:
            # The distribution has not been created yet
            return
        group = Group.objects.get(
            name="{}.{}.{}".format("container.distribution", group_type, suffix)
        )
        current_user = get_current_authenticated_user()
        if add_user_to_group:
            current_user.groups.add(group)
        self.add_for_groups(permissions, group.name)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        permissions = [
            ("modify_content_containerpushrepository", "Can modify content in a push repository"),
            (
                "manage_roles_containerpushrepository",
                "Can manage role assignments on container pushrepository",
            ),
        ]

    def finalize_new_version(self, new_version):
        """
        Ensure no added content Tags contain the same `name`.
        Args:
            new_version (pulpcore.app.models.RepositoryVersion): The incomplete RepositoryVersion to
                finalize.
        """
        remove_duplicates(new_version)
        validate_repo_version(new_version)


class ContainerDistribution(Distribution, AutoAddObjPermsMixin):
    """
    A container distribution defines how a repository version is distributed by Pulp's webserver.

    Fields:
        private (models.BooleanField): Whether the distribution is private or public.
                                       Public by default.
        descripion (models.TextField): Description of the distribution.

    Relations:
        namespace (models.ForeignKey): Namespace the distribution belonds to.
    """

    TYPE = "container"

    namespace = models.ForeignKey(
        ContainerNamespace,
        on_delete=models.CASCADE,
        related_name="container_distributions",
        null=True,
    )
    private = models.BooleanField(
        default=False,
        help_text=_(
            "Restrict pull access to explicitly authorized users. "
            "Defaults to unrestricted pull access."
        ),
    )
    description = models.TextField(null=True)

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

    def redirect_to_content_app(self, url):
        """
        Add preauthentication query string to redirect attempt.
        """
        if self.content_guard:
            url = self.content_guard.cast().preauthenticate_url(url)
        return redirect(url)

    def create_distribution_group(self, permissions, parameters):
        """
        Creates a distribution group and optionally adds the current user to it.

        The parameters are specified as a dictionary with the following keys:

        "group_type" - the type of group - owners, collaborators, or consumers
        "add_user_to_group" - a boolean that specifies if the current user should be added to the
                              group.the "model_field" for the instance.

        The permissions are object level permissions assigned to the group.
        """

        group_type = parameters["group_type"]
        add_user_to_group = parameters["add_user_to_group"]

        group = Group.objects.create(
            name="{}.{}.{}".format("container.distribution", group_type, self.pk)
        )
        current_user = get_current_authenticated_user()
        owners_group = Group.objects.get(
            name="{}.{}".format("container.distribution.owners", self.pk)
        )
        assign_perm("core.change_group", owners_group, group)
        assign_perm("core.view_group", owners_group, group)
        if add_user_to_group:
            current_user.groups.add(group)
        self.add_for_groups(permissions, group.name)

    def add_push_repository_perms_to_distribution_group(self, permissions, parameters):
        """
        Adds permissions related to ContainerPushRepository to a distribution group.

        The parameters are specified as a dictionary with the following keys:

        "group_type" - the type of group - owners, collaborators, or consumers

        The permissions are ContainerPushRepository object level permissions assigned to the
        group. The repository is the one that is associated with the ContainerDistribution.
        """

        group_type = parameters["group_type"]
        group = Group.objects.get(
            name="{}.{}.{}".format("container.distribution", group_type, self.pk)
        )
        if isinstance(self.repository, ContainerPushRepository):
            self.repository.add_for_groups(permissions, group.name)

    @hook("before_delete")
    def delete_groups_and_user_obj_perms(self):
        """
        Delete all auto created groups associated with this Distribution and user object
        permissions.
        """
        group_name_regex = r"container.distribution.(.*).{}".format(self.pk)
        Group.objects.filter(name__regex=group_name_regex).delete()
        UserObjectPermission.objects.filter(object_pk=self.pk).delete()
        GroupObjectPermission.objects.filter(object_pk=self.pk).delete()

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        permissions = [
            ("pull_containerdistribution", "Can pull from a registry repo"),
            ("push_containerdistribution", "Can push into the registry repo"),
            (
                "manage_roles_containerdistribution",
                "Can manage role assignments on container distribution",
            ),
        ]


INCOMPLETE_EXT = ".part"


def generate_filename(instance, filename):
    """Method for generating upload file name"""
    filename = os.path.join(instance.upload_dir, str(instance.pk) + INCOMPLETE_EXT)
    return time.strftime(filename)


class Upload(CoreUpload):
    """
    Model for tracking Blob uploads.
    """

    repository = models.ForeignKey(Repository, related_name="uploads", on_delete=models.CASCADE)

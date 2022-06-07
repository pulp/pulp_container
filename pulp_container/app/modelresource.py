from import_export import fields, widgets
from pulpcore.plugin.importexport import QueryModelResource, BaseContentResource
from pulpcore.plugin.modelresources import RepositoryResource

from pulp_container.app.models import (
    Blob,
    ContainerRepository,
    ContainerPushRepository,
    Manifest,
    ManifestListManifest,
    ManifestSignature,
    Tag,
)


class ContainerRepositoryResource(RepositoryResource):
    """
    A resource for importing/exporting repositories of the sync type
    """

    def set_up_queryset(self):
        """
        :return: A queryset containing one sync repository that will be exported.
        """
        return ContainerRepository.objects.filter(pk=self.repo_version.repository)

    class Meta:
        model = ContainerRepository
        exclude = RepositoryResource.Meta.exclude + ("manifest_signing_service",)


class ContainerPushRepositoryResource(RepositoryResource):
    """
    A resource for importing/exporting repositories of the push type
    """

    class PushRepositoryPulpTypeField(fields.Field):
        """A firld that exports the value of pulp_type.

        This is required since an exported push repository will be imported as a sync repository.
        Changing the model of the resource is not enough. It is also necessary to update the fields
        that still store the information about the type of a repository.
        """

        def export(self, obj):
            """Return a converted value of the pulp_type field of a push repository."""
            return "container.container"

    pulp_type = PushRepositoryPulpTypeField(column_name="pulp_type", attribute="pulp_type")

    def set_up_queryset(self):
        """
        :return: A queryset containing one push repository that will be exported.
        """
        return ContainerPushRepository.objects.filter(pk=self.repo_version.repository)

    class Meta:
        # import the repository as a repository of the sync type
        model = ContainerRepository
        exclude = RepositoryResource.Meta.exclude + ("manifest_signing_service",)


class BlobResource(BaseContentResource):
    """
    Resource for import/export of blob entities
    """

    def set_up_queryset(self):
        """
        :return: Blobs specific to a specified repo-version.
        """
        return Blob.objects.filter(pk__in=self.repo_version.content).order_by("content_ptr_id")

    class Meta:
        model = Blob
        import_id_fields = model.natural_key_fields()


class ManifestResource(BaseContentResource):
    """
    Resource for import/export of manifest entities
    """

    blobs = fields.Field(
        column_name="blobs",
        attribute="blobs",
        widget=widgets.ManyToManyWidget(Blob, field="digest"),
    )
    config_blob = fields.Field(
        column_name="config_blob",
        attribute="config_blob",
        widget=widgets.ForeignKeyWidget(Blob, field="digest"),
    )

    def set_up_queryset(self):
        """
        :return: Manifests specific to a specified repo-version.
        """
        return Manifest.objects.filter(pk__in=self.repo_version.content).order_by("content_ptr_id")

    class Meta:
        model = Manifest
        exclude = BaseContentResource.Meta.exclude + ("listed_manifests",)
        import_id_fields = model.natural_key_fields()


class ManifestListManifestResource(QueryModelResource):
    """
    Resource for import/export of manifest_list manifest m2m entries
    """

    manifest_list = fields.Field(
        column_name="manifest_list",
        attribute="manifest_list",
        widget=widgets.ForeignKeyWidget(Manifest, field="digest"),
    )
    image_manifest = fields.Field(
        column_name="image_manifest",
        attribute="image_manifest",
        widget=widgets.ForeignKeyWidget(Manifest, field="digest"),
    )

    def set_up_queryset(self):
        """
        :return: Manifests specific to a specified repo-version.
        """
        return ManifestListManifest.objects.filter(
            manifest_list__pk__in=self.repo_version.content
        ).order_by("id")

    class Meta:
        model = ManifestListManifest


class ManifestSignatureResource(BaseContentResource):
    """
    A resource for import/export of manifest signatures.
    """

    signed_manifest = fields.Field(
        column_name="signed_manifest",
        attribute="signed_manifest",
        widget=widgets.ForeignKeyWidget(Manifest, field="digest"),
    )

    def set_up_queryset(self):
        """
        Return signatures specific to a specified repo-version.
        """
        return ManifestSignature.objects.filter(pk__in=self.repo_version.content).order_by(
            "content_ptr_id"
        )

    class Meta:
        model = ManifestSignature
        import_id_fields = model.natural_key_fields()


class TagResource(BaseContentResource):
    """
    Resource for import/export of tag entities
    """

    tagged_manifest = fields.Field(
        column_name="tagged_manifest",
        attribute="tagged_manifest",
        widget=widgets.ForeignKeyWidget(Manifest, field="digest"),
    )

    def set_up_queryset(self):
        """
        :return: Tags specific to a specified repo-version.
        """
        return Tag.objects.filter(pk__in=self.repo_version.content).order_by("content_ptr_id")

    class Meta:
        model = Tag
        import_id_fields = model.natural_key_fields()


IMPORT_ORDER = [
    BlobResource,
    ManifestResource,
    ManifestListManifestResource,
    ManifestSignatureResource,
    TagResource,
    ContainerRepositoryResource,
    ContainerPushRepositoryResource,
]

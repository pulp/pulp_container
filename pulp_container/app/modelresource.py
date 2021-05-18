from import_export import fields, widgets
from pulpcore.plugin.importexport import QueryModelResource, BaseContentResource

from pulp_container.app.models import Blob, Manifest, ManifestListManifest, Tag


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


IMPORT_ORDER = [BlobResource, ManifestResource, ManifestListManifestResource, TagResource]

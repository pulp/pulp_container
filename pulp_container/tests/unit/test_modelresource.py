"""Unit tests for the import of manifest list contents through ``ManifestListManifestResource``."""

from django.test import TestCase

from pulp_container.app.modelresource import ManifestListManifestResource
from pulp_container.app.models import Manifest, ManifestListManifest
from pulp_container.constants import MEDIA_TYPE


def _manifest(char, media_type=MEDIA_TYPE.MANIFEST_V2):
    return Manifest.objects.create(
        digest=f"sha256:{char * 64}", schema_version=2, media_type=media_type
    )


def _link(manifest_list, image_manifest, architecture, **kwargs):
    return ManifestListManifest.objects.create(
        manifest_list=manifest_list,
        image_manifest=image_manifest,
        architecture=architecture,
        os="linux",
        **kwargs,
    )


def _pairs(manifest_list):
    return sorted(
        ManifestListManifest.objects.filter(manifest_list=manifest_list).values_list(
            "image_manifest__digest", flat=True
        )
    )


class TestManifestListManifestResourceImport(TestCase):
    """The rows of an export must be matched by digests, never by the exporter's row id."""

    def setUp(self):
        # content that is exported from another Pulp instance
        self.exported_list = _manifest("a", MEDIA_TYPE.MANIFEST_LIST)
        self.exported_amd64 = _manifest("b")
        self.exported_arm64 = _manifest("c")
        # content that already exists on the importing side
        self.local_list = _manifest("d", MEDIA_TYPE.MANIFEST_LIST)
        self.local_amd64 = _manifest("e")
        self.local_arm64 = _manifest("f")

    def _export_rows_of_another_instance(self, links):
        """Return a dataset like the one written by an exporter that still exports row ids."""
        links = sorted(links, key=lambda link: link.id)
        ids = [link.id for link in links]
        queryset = ManifestListManifest.objects.filter(id__in=ids).order_by("id")
        dataset = ManifestListManifestResource().export(queryset=queryset)
        if "id" not in dataset.headers:
            dataset.append_col(ids, header="id")
        return dataset

    def test_export_does_not_contain_the_row_id(self):
        link = _link(self.exported_list, self.exported_amd64, "amd64")
        queryset = ManifestListManifest.objects.filter(id=link.id)

        dataset = ManifestListManifestResource().export(queryset=queryset)

        self.assertNotIn("id", dataset.headers)
        self.assertEqual(dataset.dict[0]["manifest_list"], self.exported_list.digest)
        self.assertEqual(dataset.dict[0]["image_manifest"], self.exported_amd64.digest)

    def test_import_does_not_overwrite_links_of_an_unrelated_list(self):
        """Rows that carry the same ids as the local rows of another list must be added."""
        exported = [
            _link(self.exported_list, self.exported_amd64, "amd64"),
            _link(self.exported_list, self.exported_arm64, "arm64"),
        ]
        dataset = self._export_rows_of_another_instance(exported)
        exported_ids = [link.id for link in exported]
        ManifestListManifest.objects.filter(id__in=exported_ids).delete()

        # the importing side holds different links under exactly these ids
        _link(self.local_list, self.local_amd64, "amd64", id=exported_ids[0])
        _link(self.local_list, self.local_arm64, "arm64", id=exported_ids[1])

        result = ManifestListManifestResource().import_data(dataset, raise_errors=True)

        self.assertFalse(result.has_errors())
        self.assertEqual(
            _pairs(self.local_list), sorted([self.local_amd64.digest, self.local_arm64.digest])
        )
        self.assertEqual(
            _pairs(self.exported_list),
            sorted([self.exported_amd64.digest, self.exported_arm64.digest]),
        )
        self.assertEqual(ManifestListManifest.objects.count(), 4)

    def test_import_reuses_a_link_that_exists_under_another_id(self):
        """A pair that already exists locally must not be inserted again."""
        exported = [_link(self.exported_list, self.exported_amd64, "amd64")]
        dataset = self._export_rows_of_another_instance(exported)
        exported_id = exported[0].id
        ManifestListManifest.objects.filter(id=exported_id).delete()

        # the same pair exists locally, but under an id that does not occur in the export
        local = _link(self.exported_list, self.exported_amd64, "amd64", id=exported_id + 1000)

        result = ManifestListManifestResource().import_data(dataset, raise_errors=True)

        self.assertFalse(result.has_errors())
        remaining_ids = list(ManifestListManifest.objects.values_list("id", flat=True))
        self.assertEqual(remaining_ids, [local.id])

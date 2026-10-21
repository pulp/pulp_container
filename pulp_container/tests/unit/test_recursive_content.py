from django.test import TestCase

from pulp_container.app.models import (
    MEDIA_TYPE,
    Blob,
    BlobManifest,
    ContainerRepository,
    Manifest,
    ManifestListManifest,
)
from pulp_container.app.tasks.recursive_add import recursive_add_content
from pulp_container.app.tasks.recursive_remove import recursive_remove_content


def _make_blob(digest):
    return Blob.objects.create(digest=digest)


def _make_manifest(digest, media_type=MEDIA_TYPE.MANIFEST_V2, config_blob=None):
    return Manifest.objects.create(
        digest=digest,
        schema_version=2,
        media_type=media_type,
        config_blob=config_blob,
        data="{}",
    )


class TestRecursiveM2MQueries(TestCase):
    """Ensure recursive add/remove resolve M2M relations without values_list on M2M fields."""

    def setUp(self):
        self.repo = ContainerRepository.objects.create(name="recursive-m2m-test")

        # Two manifest lists, each with a distinct listed manifest and blob set.
        # This is the scenario where values_list("listed_manifests"/"blobs") can miss rows.
        self.config_a = _make_blob("sha256:" + "a" * 64)
        self.config_b = _make_blob("sha256:" + "b" * 64)
        self.blob_a1 = _make_blob("sha256:" + "c" * 64)
        self.blob_a2 = _make_blob("sha256:" + "d" * 64)
        self.blob_b1 = _make_blob("sha256:" + "e" * 64)

        self.manifest_a = _make_manifest("sha256:" + "1" * 64, config_blob=self.config_a)
        self.manifest_b = _make_manifest("sha256:" + "2" * 64, config_blob=self.config_b)
        BlobManifest.objects.create(manifest=self.manifest_a, manifest_blob=self.blob_a1)
        BlobManifest.objects.create(manifest=self.manifest_a, manifest_blob=self.blob_a2)
        BlobManifest.objects.create(manifest=self.manifest_b, manifest_blob=self.blob_b1)

        self.list_a = _make_manifest("sha256:" + "3" * 64, media_type=MEDIA_TYPE.MANIFEST_LIST)
        self.list_b = _make_manifest("sha256:" + "4" * 64, media_type=MEDIA_TYPE.MANIFEST_LIST)
        ManifestListManifest.objects.create(
            image_manifest=self.list_a, manifest_list=self.manifest_a
        )
        ManifestListManifest.objects.create(
            image_manifest=self.list_b, manifest_list=self.manifest_b
        )

    def test_recursive_add_includes_all_listed_manifests_and_blobs(self):
        recursive_add_content(self.repo.pk, [self.list_a.pk, self.list_b.pk])

        content_pks = set(self.repo.latest_version().content.values_list("pk", flat=True))
        expected = {
            self.list_a.pk,
            self.list_b.pk,
            self.manifest_a.pk,
            self.manifest_b.pk,
            self.config_a.pk,
            self.config_b.pk,
            self.blob_a1.pk,
            self.blob_a2.pk,
            self.blob_b1.pk,
        }
        self.assertTrue(expected.issubset(content_pks), content_pks)

    def test_recursive_remove_drops_unshared_listed_content(self):
        # Seed the repository with both lists and their related content.
        recursive_add_content(self.repo.pk, [self.list_a.pk, self.list_b.pk])

        # Remove only list_b; list_a's tree must remain, list_b's tree must go.
        recursive_remove_content(self.repo.pk, [self.list_b.pk])

        content_pks = set(self.repo.latest_version().content.values_list("pk", flat=True))
        remaining = {
            self.list_a.pk,
            self.manifest_a.pk,
            self.config_a.pk,
            self.blob_a1.pk,
            self.blob_a2.pk,
        }
        removed = {
            self.list_b.pk,
            self.manifest_b.pk,
            self.config_b.pk,
            self.blob_b1.pk,
        }
        self.assertTrue(remaining.issubset(content_pks), content_pks)
        self.assertTrue(removed.isdisjoint(content_pks), content_pks)

"""Unit tests for push-path content unit collection used with add_and_remove."""

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from pulp_container.app.models import Blob, BlobManifest, Manifest, ManifestListManifest, Tag
from pulp_container.app.utils import get_content_units_to_add
from pulp_container.constants import MEDIA_TYPE


def _digest(n: int) -> str:
    return f"sha256:{n:064x}"


def _create_manifest(*, digest, media_type, config_blob=None, schema_version=2):
    return Manifest.objects.create(
        digest=digest,
        media_type=media_type,
        schema_version=schema_version,
        config_blob=config_blob,
        data="{}",
    )


class TestGetContentUnitsToAdd(TestCase):
    """Exercise get_content_units_to_add query behavior."""

    def test_simple_manifest_includes_config_and_blobs(self):
        config = Blob.objects.create(digest=_digest(1))
        layer = Blob.objects.create(digest=_digest(2))
        manifest = _create_manifest(
            digest=_digest(3),
            media_type=MEDIA_TYPE.MANIFEST_V2,
            config_blob=config,
        )
        BlobManifest.objects.create(manifest=manifest, manifest_blob=layer)
        tag = Tag.objects.create(name="latest", tagged_manifest=manifest)

        units = get_content_units_to_add(manifest, tag)

        self.assertEqual(
            set(units),
            {str(manifest.pk), str(tag.pk), str(config.pk), str(layer.pk)},
        )

    def test_manifest_list_uses_bulk_blob_query(self):
        config_a = Blob.objects.create(digest=_digest(10))
        config_b = Blob.objects.create(digest=_digest(11))
        layer_a = Blob.objects.create(digest=_digest(12))
        layer_b = Blob.objects.create(digest=_digest(13))

        child_a = _create_manifest(
            digest=_digest(20),
            media_type=MEDIA_TYPE.MANIFEST_V2,
            config_blob=config_a,
        )
        child_b = _create_manifest(
            digest=_digest(21),
            media_type=MEDIA_TYPE.MANIFEST_V2,
            config_blob=config_b,
        )
        BlobManifest.objects.create(manifest=child_a, manifest_blob=layer_a)
        BlobManifest.objects.create(manifest=child_b, manifest_blob=layer_b)

        index = _create_manifest(
            digest=_digest(30),
            media_type=MEDIA_TYPE.MANIFEST_LIST,
        )
        # image_manifest is the list; manifest_list is the listed child (through_fields order).
        ManifestListManifest.objects.create(image_manifest=index, manifest_list=child_a)
        ManifestListManifest.objects.create(image_manifest=index, manifest_list=child_b)

        with CaptureQueriesContext(connection) as ctx:
            units = get_content_units_to_add(index)

        # One query for listed manifests, one bulk query for related blobs — not N+1.
        self.assertEqual(len(ctx.captured_queries), 2, [q["sql"] for q in ctx.captured_queries])

        self.assertEqual(
            set(units),
            {
                str(index.pk),
                str(child_a.pk),
                str(child_b.pk),
                str(config_a.pk),
                str(config_b.pk),
                str(layer_a.pk),
                str(layer_b.pk),
            },
        )

    def test_all_returned_pks_are_strings(self):
        config = Blob.objects.create(digest=_digest(40))
        manifest = _create_manifest(
            digest=_digest(41),
            media_type=MEDIA_TYPE.MANIFEST_OCI,
            config_blob=config,
        )
        units = get_content_units_to_add(manifest)
        self.assertTrue(all(isinstance(pk, str) for pk in units))


class TestTagReplacementFilter(TestCase):
    """Ensure tag replacement filters by Tag.name, not Tag.__str__."""

    def test_filter_by_tag_name_matches_existing_tag(self):
        manifest_old = _create_manifest(
            digest=_digest(50),
            media_type=MEDIA_TYPE.MANIFEST_V2,
        )
        manifest_new = _create_manifest(
            digest=_digest(51),
            media_type=MEDIA_TYPE.MANIFEST_V2,
        )
        old_tag = Tag.objects.create(name="latest", tagged_manifest=manifest_old)
        new_tag = Tag.objects.create(name="latest", tagged_manifest=manifest_new)

        # Correct filter used by the push path after optimization.
        matched = Tag.objects.filter(name=new_tag.name).exclude(tagged_manifest=manifest_new)
        self.assertQuerySetEqual(matched, [old_tag], ordered=False)

        # Passing the Tag instance would coerce via MasterModel.__str__ and miss.
        broken = Tag.objects.filter(name=new_tag).exclude(tagged_manifest=manifest_new)
        self.assertFalse(broken.exists())

"""Unit tests for cosign companion tag helpers on ContainerFirstStage."""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from pulp_container.app.tasks.sync_stages import COSIGN_TAG_SUFFIXES, ContainerFirstStage
from pulp_container.constants import MEDIA_TYPE


def _bare_cosign_digest() -> tuple[str, str]:
    """Return (tag_name, docker digest form) for a 71-char V3 cosign tag name."""
    tag = "sha256-" + "a" * 64
    digest = "sha256:" + "a" * 64
    return tag, digest


class TestCosignCompanionHelpers(unittest.IsolatedAsyncioTestCase):
    """Exercise cosign tagging helpers without the full sync pipeline."""

    def setUp(self):
        remote = MagicMock()
        remote.policy = MagicMock()
        remote.namespaced_upstream_name = "library/test"
        remote.url = "https://registry.example/"
        remote.get_downloader = MagicMock()

        self.stage = ContainerFirstStage(remote=remote, signed_only=False)

    def test_is_cosign_companion_tag_v2_suffixes(self):
        """V2 companions use sha256-<digest>.<suffix> where suffix is .sig / .att / .sbom."""
        tag, _ = _bare_cosign_digest()
        for suffix in COSIGN_TAG_SUFFIXES:
            with self.subTest(suffix=suffix):
                name = f"{tag}{suffix}"
                self.assertTrue(
                    self.stage._is_cosign_companion_tag(name, MEDIA_TYPE.MANIFEST_LIST, {})
                )

    def test_is_cosign_companion_tag_v2_not_companion_with_wrong_suffix(self):
        tag, _ = _bare_cosign_digest()
        self.assertFalse(
            self.stage._is_cosign_companion_tag(f"{tag}.other", MEDIA_TYPE.MANIFEST_LIST, {})
        )

    def test_is_cosign_companion_tag_non_sha256_prefix(self):
        self.assertFalse(
            self.stage._is_cosign_companion_tag("latest", MEDIA_TYPE.MANIFEST_LIST, {})
        )

    def test_is_cosign_companion_tag_v3_oci_index_with_artifact_types(self):
        tag, _ = _bare_cosign_digest()
        content = {
            "manifests": [
                {"artifactType": "application/vnd.dev.cosign.simplesigning.v1+json"},
                {"artifactType": "application/vnd.oci.image.config.v1+json"},
            ]
        }
        self.assertTrue(self.stage._is_cosign_companion_tag(tag, MEDIA_TYPE.INDEX_OCI, content))

    def test_is_cosign_companion_tag_v3_requires_all_artifact_types(self):
        tag, _ = _bare_cosign_digest()
        content = {
            "manifests": [
                {"artifactType": "application/vnd.dev.cosign.simplesigning.v1+json"},
                {"mediaType": "application/vnd.oci.image.manifest.v1+json"},
            ]
        }
        self.assertFalse(self.stage._is_cosign_companion_tag(tag, MEDIA_TYPE.INDEX_OCI, content))

    def test_is_cosign_companion_tag_v3_wrong_media_type(self):
        tag, _ = _bare_cosign_digest()
        content = {
            "manifests": [{"artifactType": "application/vnd.dev.cosign.simplesigning.v1+json"}]
        }
        self.assertFalse(
            self.stage._is_cosign_companion_tag(tag, MEDIA_TYPE.MANIFEST_LIST, content)
        )

    def test_find_cosign_companion_tags_filters_by_synced_digests(self):
        tag_sig, digest = _bare_cosign_digest()
        tag_sig = f"{tag_sig}.sig"
        tag_att = tag_sig.replace(".sig", ".att")

        self.stage._cosign_tags = [tag_sig, tag_att, "sha256-" + "b" * 64 + ".sig"]
        self.stage._synced_digests = {digest}

        found = self.stage._find_cosign_companion_tags()
        self.assertCountEqual(found, [tag_sig, tag_att])

    def test_find_cosign_companion_tags_empty_when_nothing_synced(self):
        tag_sig, _ = _bare_cosign_digest()
        self.stage._cosign_tags = [f"{tag_sig}.sig"]
        self.stage._synced_digests = set()
        self.assertEqual(self.stage._find_cosign_companion_tags(), [])

    async def test_has_cosign_signature_true_when_sig_tag_present(self):
        _, digest = _bare_cosign_digest()
        cosign_key = digest.replace("sha256:", "sha256-")
        self.stage._cosign_tags = [f"{cosign_key}.sig"]

        self.assertTrue(await self.stage._has_cosign_signature(digest))
        self.stage.remote.get_downloader.assert_not_called()

    async def test_has_cosign_signature_true_after_fetching_v3_index(self):
        tag, digest = _bare_cosign_digest()
        self.stage._cosign_tags = [tag]

        content_data = {
            "manifests": [
                {"artifactType": "application/vnd.dev.cosign.simplesigning.v1+json"},
            ]
        }
        raw = '{"manifests":[]}'

        mock_response = MagicMock()
        mock_response.url = f"https://registry.example/v2/foo/manifests/{tag}"

        self.stage._download_manifest_data = AsyncMock(
            return_value=(content_data, raw, mock_response)
        )

        with patch(
            "pulp_container.app.tasks.sync_stages.determine_media_type",
            return_value=MEDIA_TYPE.INDEX_OCI,
        ):
            self.assertTrue(await self.stage._has_cosign_signature(digest))

        self.stage._download_manifest_data.assert_awaited_once()

    async def test_has_cosign_signature_false_when_bare_tag_not_companion(self):
        tag, digest = _bare_cosign_digest()
        self.stage._cosign_tags = [tag]

        content_data = {"manifests": []}
        raw = "{}"
        mock_response = MagicMock()
        mock_response.url = f"https://registry.example/v2/foo/manifests/{tag}"

        self.stage._download_manifest_data = AsyncMock(
            return_value=(content_data, raw, mock_response)
        )

        with patch(
            "pulp_container.app.tasks.sync_stages.determine_media_type",
            return_value=MEDIA_TYPE.INDEX_OCI,
        ):
            self.assertFalse(await self.stage._has_cosign_signature(digest))

    async def test_has_cosign_signature_false_when_no_cosign_tags(self):
        _, digest = _bare_cosign_digest()
        self.stage._cosign_tags = []
        self.assertFalse(await self.stage._has_cosign_signature(digest))


if __name__ == "__main__":
    unittest.main()

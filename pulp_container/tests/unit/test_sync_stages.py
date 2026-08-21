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


class TestBypassTaglistOptimization(unittest.IsolatedAsyncioTestCase):
    """Test bypass logic for skipping /tags/list enumeration."""

    def setUp(self):
        remote = MagicMock()
        remote.policy = MagicMock()
        remote.namespaced_upstream_name = "library/test"
        remote.url = "https://registry.example/"
        remote.get_downloader = MagicMock()
        remote.include_tags = None
        remote.exclude_tags = None
        remote.auto_discover_cosign = True

        self.stage = ContainerFirstStage(remote=remote, signed_only=False, mirror=False)

    def test_can_bypass_with_specific_digests_only(self):
        """Bypass activates when include_tags contains only sha256 digests."""
        self.stage.remote.include_tags = [
            "sha256:abc123",
            "sha256:def456",
        ]
        self.stage.remote.exclude_tags = None
        self.assertTrue(self.stage._can_bypass_taglist())

    def test_cannot_bypass_without_includes(self):
        """Bypass does not activate when include_tags is empty."""
        self.stage.remote.include_tags = None
        self.stage.remote.exclude_tags = None
        self.assertFalse(self.stage._can_bypass_taglist())

    def test_cannot_bypass_with_tag_names(self):
        """Bypass does not activate when include_tags contains tag names (not digests)."""
        self.stage.remote.include_tags = ["manifest_a", "latest"]
        self.stage.remote.exclude_tags = None
        self.assertFalse(self.stage._can_bypass_taglist())

    def test_cannot_bypass_with_mixed_digests_and_tag_names(self):
        """Bypass does not activate when include_tags mixes digests and tag names."""
        self.stage.remote.include_tags = ["sha256:abc123", "manifest_a"]
        self.stage.remote.exclude_tags = None
        self.assertFalse(self.stage._can_bypass_taglist())

    def test_cannot_bypass_with_wildcards(self):
        """Bypass does not activate when include_tags contains wildcards."""
        self.stage.remote.include_tags = ["v4.0*", "sha256:abc123"]
        self.stage.remote.exclude_tags = None
        self.assertFalse(self.stage._can_bypass_taglist())

    def test_cannot_bypass_in_mirror_mode(self):
        """Bypass does not activate in mirror mode."""
        self.stage.mirror = True
        self.stage.remote.include_tags = ["sha256:abc123"]
        self.stage.remote.exclude_tags = None
        self.assertFalse(self.stage._can_bypass_taglist())

    def test_can_bypass_with_harmless_excludes(self):
        """Bypass activates when excludes won't match sha256 includes."""
        self.stage.remote.include_tags = ["sha256:abc123", "sha256:def456"]
        self.stage.remote.exclude_tags = ["*-source"]
        self.assertTrue(self.stage._can_bypass_taglist())

    def test_cannot_bypass_with_harmful_excludes(self):
        """Bypass does not activate when excludes could match digest includes."""
        self.stage.remote.include_tags = ["sha256:abc123", "sha256:def456"]
        self.stage.remote.exclude_tags = ["sha256:*"]
        self.assertFalse(self.stage._can_bypass_taglist())

    def test_cannot_bypass_with_overlapping_excludes(self):
        """Bypass does not activate when exclude pattern matches an include."""
        self.stage.remote.include_tags = ["sha256:abc123", "v4.0-source"]
        self.stage.remote.exclude_tags = ["*-source"]
        self.assertFalse(self.stage._can_bypass_taglist())

    async def test_tag_exists_returns_true_on_200(self):
        """_tag_exists returns True when HEAD request succeeds."""
        downloader = MagicMock()
        mock_result = AsyncMock()
        mock_result.status_code = 200
        downloader.run = AsyncMock(return_value=mock_result)
        self.stage.remote.get_downloader.return_value = downloader

        result = await self.stage._tag_exists("test-tag")
        self.assertTrue(result)

    async def test_tag_exists_returns_false_on_404(self):
        """_tag_exists returns False when tag doesn't exist."""
        downloader = MagicMock()
        downloader.run = AsyncMock(side_effect=Exception("404"))
        self.stage.remote.get_downloader.return_value = downloader

        result = await self.stage._tag_exists("missing-tag")
        self.assertFalse(result)

    async def test_discover_cosign_companions_probes_variants(self):
        """Discover cosign companions probes .sig, .att, .sbom variants."""
        synced_digests = {"sha256:abc123"}
        self.stage._synced_digests = synced_digests

        # Mock _tag_exists to return True for .sig variant only
        async def mock_tag_exists(tag):
            return tag == "sha256-abc123.sig"

        self.stage._tag_exists = AsyncMock(side_effect=mock_tag_exists)

        companions = await self.stage._discover_cosign_companions_without_taglist(synced_digests)

        self.assertEqual(len(companions), 1)
        self.assertEqual(companions[0], "sha256-abc123.sig")

    async def test_discover_cosign_companions_returns_empty_when_none_exist(self):
        """Discover returns empty list when no companion tags exist."""
        synced_digests = {"sha256:abc123"}
        self.stage._synced_digests = synced_digests
        self.stage._tag_exists = AsyncMock(return_value=False)

        companions = await self.stage._discover_cosign_companions_without_taglist(synced_digests)

        self.assertEqual(len(companions), 0)


if __name__ == "__main__":
    unittest.main()

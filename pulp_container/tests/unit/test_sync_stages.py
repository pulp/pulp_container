"""Unit tests for ContainerFirstStage: cosign companion tag helpers and tag list bypass."""

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


class TestParseIncludeEntry(unittest.TestCase):
    """Test _parse_include_entry static method."""

    def test_plain_digest(self):
        digest, alias = ContainerFirstStage._parse_include_entry("sha256:" + "a" * 64)
        assert digest == "sha256:" + "a" * 64
        assert alias is None

    def test_named_alias(self):
        entry = "cli=sha256:" + "b" * 64
        digest, alias = ContainerFirstStage._parse_include_entry(entry)
        assert digest == "sha256:" + "b" * 64
        assert alias == "cli"

    def test_named_alias_with_hyphens(self):
        entry = "cluster-dns-operator=sha256:" + "c" * 64
        digest, alias = ContainerFirstStage._parse_include_entry(entry)
        assert digest == "sha256:" + "c" * 64
        assert alias == "cluster-dns-operator"

    def test_non_digest_tag(self):
        digest, alias = ContainerFirstStage._parse_include_entry("latest")
        assert digest is None
        assert alias is None

    def test_wildcard_pattern(self):
        digest, alias = ContainerFirstStage._parse_include_entry("v1.*")
        assert digest is None
        assert alias is None

    def test_name_equals_non_digest(self):
        digest, alias = ContainerFirstStage._parse_include_entry("name=latest")
        assert digest is None
        assert alias is None


class TestCanBypassTaglist(unittest.TestCase):
    """Test _can_bypass_taglist decision logic."""

    def _make_stage(self, includes=None, excludes=None, mirror=False):
        remote = MagicMock()
        remote.policy = MagicMock()
        remote.includes = includes
        remote.excludes = excludes
        stage = ContainerFirstStage(remote=remote, signed_only=False, mirror=mirror)
        return stage

    def test_all_digests_no_excludes(self):
        stage = self._make_stage(includes=["sha256:" + "a" * 64, "sha256:" + "b" * 64])
        assert stage._can_bypass_taglist() is True

    def test_mixed_digests_and_aliases(self):
        stage = self._make_stage(
            includes=[
                "sha256:" + "a" * 64,
                "cli=sha256:" + "b" * 64,
            ]
        )
        assert stage._can_bypass_taglist() is True

    def test_non_digest_entry_prevents_bypass(self):
        stage = self._make_stage(includes=["latest", "sha256:" + "a" * 64])
        assert stage._can_bypass_taglist() is False

    def test_empty_includes_prevents_bypass(self):
        stage = self._make_stage(includes=[])
        assert stage._can_bypass_taglist() is False

    def test_none_includes_prevents_bypass(self):
        stage = self._make_stage(includes=None)
        assert stage._can_bypass_taglist() is False

    def test_mirror_mode_prevents_bypass(self):
        stage = self._make_stage(includes=["sha256:" + "a" * 64], mirror=True)
        assert stage._can_bypass_taglist() is False

    def test_harmless_source_exclude(self):
        stage = self._make_stage(
            includes=["sha256:" + "a" * 64],
            excludes=["*-source"],
        )
        assert stage._can_bypass_taglist() is True

    def test_non_harmless_exclude_prevents_bypass(self):
        stage = self._make_stage(
            includes=["sha256:" + "a" * 64],
            excludes=["sha256:" + "a" * 64],
        )
        assert stage._can_bypass_taglist() is False

    def test_wildcard_exclude_not_matching_digests(self):
        stage = self._make_stage(
            includes=["sha256:" + "a" * 64],
            excludes=["*-beta"],
        )
        assert stage._can_bypass_taglist() is True


class TestDiscoverCosignCompanionsWithoutTaglist(unittest.IsolatedAsyncioTestCase):
    """Test _discover_cosign_companions_without_taglist HEAD-probe logic."""

    def setUp(self):
        remote = MagicMock()
        remote.policy = MagicMock()
        remote.namespaced_upstream_name = "library/test"
        remote.url = "https://registry.example/"
        remote.get_downloader = MagicMock()
        self.stage = ContainerFirstStage(remote=remote, signed_only=False)

    async def test_probes_all_cosign_patterns(self):
        digest = "sha256:" + "a" * 64
        hex_part = "a" * 64

        self.stage._tag_exists = AsyncMock(return_value=True)
        companions = await self.stage._discover_cosign_companions_without_taglist([digest])

        expected_tags = {
            f"sha256-{hex_part}.sig",
            f"sha256-{hex_part}.att",
            f"sha256-{hex_part}.sbom",
            f"sha256-{hex_part}",
        }
        assert set(companions) == expected_tags

    async def test_returns_only_existing_tags(self):
        digest = "sha256:" + "a" * 64
        hex_part = "a" * 64

        async def selective_exists(tag):
            return tag.endswith(".sig")

        self.stage._tag_exists = selective_exists
        companions = await self.stage._discover_cosign_companions_without_taglist([digest])

        assert companions == [f"sha256-{hex_part}.sig"]

    async def test_skips_non_sha256_digests(self):
        self.stage._tag_exists = AsyncMock(return_value=True)
        companions = await self.stage._discover_cosign_companions_without_taglist(["not-a-digest"])
        assert companions == []
        self.stage._tag_exists.assert_not_called()

    async def test_empty_input(self):
        self.stage._tag_exists = AsyncMock(return_value=True)
        companions = await self.stage._discover_cosign_companions_without_taglist([])
        assert companions == []


class TestTagExistsHeadProbe(unittest.IsolatedAsyncioTestCase):
    """Test _tag_exists HEAD request behavior."""

    def setUp(self):
        remote = MagicMock()
        remote.policy = MagicMock()
        remote.namespaced_upstream_name = "library/test"
        remote.url = "https://registry.example/"
        self.stage = ContainerFirstStage(remote=remote, signed_only=False)

    async def test_returns_true_on_success(self):
        mock_downloader = AsyncMock()
        mock_downloader.run = AsyncMock(return_value=MagicMock())
        self.stage.remote.get_downloader = MagicMock(return_value=mock_downloader)

        result = await self.stage._tag_exists("sha256-aaa.sig")
        assert result is True

    async def test_returns_false_on_exception(self):
        mock_downloader = AsyncMock()
        mock_downloader.run = AsyncMock(side_effect=Exception("404 Not Found"))
        self.stage.remote.get_downloader = MagicMock(return_value=mock_downloader)

        result = await self.stage._tag_exists("sha256-nonexistent.sig")
        assert result is False


if __name__ == "__main__":
    unittest.main()

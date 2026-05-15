"""Tests that sync container plugin repositories."""

from urllib.parse import quote

import pytest

from pulpcore.tests.functional.utils import PulpTaskError

from pulp_container.constants import MANIFEST_TYPE, MEDIA_TYPE
from pulp_container.tests.functional.constants import (
    PULP_COSIGN_COMPANION_TAGS,
    PULP_COSIGN_TAGS_MANIFEST_A_DIGEST,
    PULP_COSIGN_TAGS_MANIFEST_B_DIGEST,
    PULP_COSIGN_TAGS_MANIFEST_C_DIGEST,
    PULP_FIXTURE_1,
    PULP_FIXTURE_1_MANIFEST_A_DIGEST,
    PULP_HELLO_WORLD_LINUX_AMD64_DIGEST,
    PULP_LABELED_FIXTURE,
    REGISTRY_V2_FEED_URL,
)


def _cosign_registry_tag_name(image_digest: str) -> str:
    """Cosign companion tags use ``sha256-<hex>`` instead of ``sha256:<hex>``."""
    return image_digest.replace("sha256:", "sha256-", 1)


# there is a manifest list and a listed manifest
BOOTABLE_MANIFESTS_COUNT = 2


@pytest.fixture
def synced_container_repository_factory(
    container_repository_factory, container_remote_factory, container_repository_api, container_sync
):
    def _synced_container_repository_factory(
        url=REGISTRY_V2_FEED_URL, include_tags=None, exclude_tags=None, upstream_name=PULP_FIXTURE_1
    ):
        """Sync a new repository with the included tags passed as an argument."""
        remote = container_remote_factory(
            url,
            upstream_name=upstream_name,
            include_tags=include_tags,
            exclude_tags=exclude_tags,
        )

        repository = container_repository_factory()

        container_sync(repository, remote)
        synced_repository = container_repository_api.read(repository.pulp_href)

        return synced_repository

    return _synced_container_repository_factory


@pytest.mark.parallel
def test_basic_sync(
    check_manifest_fields,
    check_manifest_arch_os_size,
    container_repo,
    container_remote,
    container_repository_api,
    container_sync,
    container_manifest_api,
    has_pulp_plugin,
):
    repo_version = container_sync(container_repo, container_remote).created_resources[0]
    repository = container_repository_api.read(container_repo.pulp_href)

    assert "versions/1/" in repository.latest_version_href

    latest_version_href = repository.latest_version_href
    media_type = MEDIA_TYPE.MANIFEST_V2
    if has_pulp_plugin("core", min="3.70", max="3.85"):
        media_type = quote(media_type)

    assert check_manifest_fields(
        manifest_filters={
            "repository_version": repo_version,
            "media_type": [media_type],
            "digest": PULP_HELLO_WORLD_LINUX_AMD64_DIGEST,
        },
        fields={"type": MANIFEST_TYPE.IMAGE},
    )

    container_sync(
        container_repo, container_remote
    )  # We expect that this second sync doesn't create a new repo version
    repository = container_repository_api.read(repository.pulp_href)

    assert repository.latest_version_href == latest_version_href

    manifest = container_manifest_api.list(
        repository_version=repo_version,
        media_type=[media_type],
        digest=PULP_HELLO_WORLD_LINUX_AMD64_DIGEST,
    )
    check_manifest_arch_os_size(manifest)


@pytest.mark.parallel
def test_sync_labelled_image(
    container_remote_factory,
    container_repo,
    container_sync,
    container_tag_api,
    container_manifest_api,
):
    """Test syncing an image containing labels and assert on their availability in the ViewSet."""
    remote = container_remote_factory(upstream_name=PULP_LABELED_FIXTURE)
    repo_version = container_sync(container_repo, remote).created_resources[0]

    tag = container_tag_api.list(repository_version=repo_version).results[0]
    manifest_list = container_manifest_api.read(tag.tagged_manifest)
    assert manifest_list.is_bootable
    assert not manifest_list.is_flatpak

    manifest = container_manifest_api.read(manifest_list.listed_manifests[0])
    keys = sorted(["org.opencontainers.image.base.name", "org.opencontainers.image.base.digest"])
    assert keys == sorted(manifest.annotations.keys())

    count = container_manifest_api.list(repository_version=repo_version, is_bootable=True).count
    assert count == BOOTABLE_MANIFESTS_COUNT

    count = container_manifest_api.list(repository_version=repo_version, is_bootable=False).count
    assert count == 0


def test_sync_reclaim_resync(
    container_repo,
    container_remote,
    container_sync,
    monitor_task,
    pulpcore_bindings,
):
    """Check if re-syncing the content after the reclamation ends with no error."""
    container_sync(container_repo, container_remote)
    monitor_task(pulpcore_bindings.RepositoriesReclaimSpaceApi.reclaim({"repo_hrefs": ["*"]}).task)
    container_sync(container_repo, container_remote)


@pytest.mark.parallel
def test_sync_invalid_url(synced_container_repository_factory):
    with pytest.raises(PulpTaskError):
        synced_container_repository_factory(url="http://i-am-an-invalid-url.com/invalid/")


@pytest.mark.parallel
@pytest.mark.parametrize(
    "include_tags, expected_tags",
    [
        (["manifest_a", "non_existing_manifest"], ["manifest_a"]),
        (["manifest_a", "manifest_b", "manifest_c"], ["manifest_a", "manifest_b", "manifest_c"]),
        (
            ["ml_??", "manifest*"],
            [
                "ml_iv",
                "ml_ii",
                "manifest_a",
                "manifest_b",
                "manifest_c",
                "manifest_d",
                "manifest_e",
            ],
        ),
    ],
)
def test_tag_filtering_operations(
    include_tags,
    expected_tags,
    synced_container_repository_factory,
    container_repository_api,
    container_tag_api,
):
    synced_repo = synced_container_repository_factory(include_tags=include_tags)

    latest_repo_version = container_repository_api.read(synced_repo.pulp_href).latest_version_href
    tags = container_tag_api.list(repository_version=latest_repo_version).results

    assert set(expected_tags) == {tag.name for tag in tags}


@pytest.mark.parallel
def test_sync_with_complex_filtering(
    synced_container_repository_factory, container_repository_api, container_tag_api
):
    """Test sync repository with included and excluded tags that use wildcards."""
    include_tags = [
        "manifest_a",
        "manifest_c",
        "manifest_e",
    ]
    synced_repo = synced_container_repository_factory(
        include_tags=["manifest_*"], exclude_tags=["*_[bd]"]
    )

    tags = container_tag_api.list(repository_version=synced_repo.latest_version_href).results

    assert sorted(include_tags) == sorted(tag.name for tag in tags)


@pytest.mark.parallel
def test_sync_cosign_companion_tags(
    synced_container_repository_factory, container_tag_api, container_manifest_api
):
    """Test syncing a repository with cosign companion tags."""
    synced_repo = synced_container_repository_factory(upstream_name=PULP_COSIGN_COMPANION_TAGS)

    tags = container_tag_api.list(repository_version=synced_repo.latest_version_href)
    manifests = container_manifest_api.list(repository_version=synced_repo.latest_version_href)
    assert tags.count == 9
    cr = _cosign_registry_tag_name
    expected_tag_names = {
        "manifest_a",
        "manifest_b",
        "manifest_c",
        "manifest_d",
        f"{cr(PULP_COSIGN_TAGS_MANIFEST_A_DIGEST)}.sig",
        f"{cr(PULP_COSIGN_TAGS_MANIFEST_A_DIGEST)}.att",
        f"{cr(PULP_COSIGN_TAGS_MANIFEST_B_DIGEST)}.sig",
        cr(PULP_COSIGN_TAGS_MANIFEST_B_DIGEST),
        cr(PULP_COSIGN_TAGS_MANIFEST_C_DIGEST),
    }
    assert {t.name for t in tags.results} == expected_tag_names
    assert manifests.count == 13


@pytest.mark.parallel
def test_sync_cosign_companion_tags_with_filtering(
    synced_container_repository_factory, container_tag_api, container_manifest_api
):
    """Test syncing a repository with cosign companion tags and filtering."""
    synced_repo = synced_container_repository_factory(
        upstream_name=PULP_COSIGN_COMPANION_TAGS, include_tags=["manifest_a"]
    )

    tags = container_tag_api.list(repository_version=synced_repo.latest_version_href)
    manifests = container_manifest_api.list(repository_version=synced_repo.latest_version_href)
    assert tags.count == 3
    cr = _cosign_registry_tag_name
    assert {t.name for t in tags.results} == {
        "manifest_a",
        f"{cr(PULP_COSIGN_TAGS_MANIFEST_A_DIGEST)}.sig",
        f"{cr(PULP_COSIGN_TAGS_MANIFEST_A_DIGEST)}.att",
    }
    assert manifests.count == 3

    synced_repo = synced_container_repository_factory(
        upstream_name=PULP_COSIGN_COMPANION_TAGS, include_tags=["manifest_b"]
    )

    tags = container_tag_api.list(repository_version=synced_repo.latest_version_href)
    manifests = container_manifest_api.list(repository_version=synced_repo.latest_version_href)
    assert tags.count == 3
    assert {t.name for t in tags.results} == {
        "manifest_b",
        f"{cr(PULP_COSIGN_TAGS_MANIFEST_B_DIGEST)}.sig",
        cr(PULP_COSIGN_TAGS_MANIFEST_B_DIGEST),
    }
    assert manifests.count == 5  # The V3 sig is a manifest list with 2 manifests

    synced_repo = synced_container_repository_factory(
        upstream_name=PULP_COSIGN_COMPANION_TAGS, exclude_tags=["manifest_a"]
    )

    tags = container_tag_api.list(repository_version=synced_repo.latest_version_href)
    manifests = container_manifest_api.list(repository_version=synced_repo.latest_version_href)
    assert tags.count == 6
    assert {t.name for t in tags.results} == {
        "manifest_b",
        "manifest_c",
        "manifest_d",
        f"{cr(PULP_COSIGN_TAGS_MANIFEST_B_DIGEST)}.sig",
        cr(PULP_COSIGN_TAGS_MANIFEST_B_DIGEST),
        cr(PULP_COSIGN_TAGS_MANIFEST_C_DIGEST),
    }
    assert manifests.count == 10


@pytest.mark.parallel
def test_sync_by_digest_includes(
    container_repository_factory,
    container_remote_factory,
    container_repository_api,
    container_sync,
    container_tag_api,
    container_manifest_api,
):
    """Test that a digest entry in 'includes' syncs a manifest directly without a tag."""
    remote = container_remote_factory(
        upstream_name=PULP_FIXTURE_1,
        includes=[PULP_FIXTURE_1_MANIFEST_A_DIGEST],
    )
    repository = container_repository_factory()
    container_sync(repository, remote)
    repo_version = container_repository_api.read(repository.pulp_href).latest_version_href

    tags = container_tag_api.list(repository_version=repo_version)
    manifests = container_manifest_api.list(repository_version=repo_version)

    # No tags — digest entries in includes sync manifests without tag association
    assert tags.count == 0
    assert manifests.count == 1
    assert manifests.results[0].digest == PULP_FIXTURE_1_MANIFEST_A_DIGEST


@pytest.mark.parallel
def test_sync_digest_includes_pulls_cosign_companions(
    container_repository_factory,
    container_remote_factory,
    container_repository_api,
    container_sync,
    container_tag_api,
    container_manifest_api,
):
    """Test that digest entries in 'includes' also pull in cosign companion tags.

    pulp/cosign-tags and pulp/test-fixture-1 share the same manifest_a/b/c/d digests.
    manifest_a has two cosign companions (.sig v2, .att v2).
    manifest_b has two cosign companions (.sig v2, sha256-<digest> v3 index with 2 sub-manifests).
    """
    cr = _cosign_registry_tag_name

    # --- manifest_a: two v2 cosign companions ---
    remote_a = container_remote_factory(
        upstream_name=PULP_COSIGN_COMPANION_TAGS,
        includes=[PULP_COSIGN_TAGS_MANIFEST_A_DIGEST],
    )
    repo_a = container_repository_factory()
    container_sync(repo_a, remote_a)
    ver_a = container_repository_api.read(repo_a.pulp_href).latest_version_href

    tags_a = container_tag_api.list(repository_version=ver_a)
    manifests_a = container_manifest_api.list(repository_version=ver_a)

    # The primary manifest has no tag; companions get tags as usual
    assert tags_a.count == 2
    assert {t.name for t in tags_a.results} == {
        f"{cr(PULP_COSIGN_TAGS_MANIFEST_A_DIGEST)}.sig",
        f"{cr(PULP_COSIGN_TAGS_MANIFEST_A_DIGEST)}.att",
    }
    # manifest_a itself + .sig manifest + .att manifest
    assert manifests_a.count == 3

    # --- manifest_b: one v2 + one v3 (manifest list) cosign companion ---
    remote_b = container_remote_factory(
        upstream_name=PULP_COSIGN_COMPANION_TAGS,
        includes=[PULP_COSIGN_TAGS_MANIFEST_B_DIGEST],
    )
    repo_b = container_repository_factory()
    container_sync(repo_b, remote_b)
    ver_b = container_repository_api.read(repo_b.pulp_href).latest_version_href

    tags_b = container_tag_api.list(repository_version=ver_b)
    manifests_b = container_manifest_api.list(repository_version=ver_b)

    assert tags_b.count == 2
    assert {t.name for t in tags_b.results} == {
        f"{cr(PULP_COSIGN_TAGS_MANIFEST_B_DIGEST)}.sig",
        cr(PULP_COSIGN_TAGS_MANIFEST_B_DIGEST),
    }
    # manifest_b + .sig manifest + v3 manifest list + 2 v3 sub-manifests
    assert manifests_b.count == 5


@pytest.mark.parallel
def test_sync_mixed_tags_and_digests_in_includes(
    container_repository_factory,
    container_remote_factory,
    container_repository_api,
    container_sync,
    container_tag_api,
    container_manifest_api,
):
    """Test that 'includes' can mix tag patterns and digests in a single sync."""
    cr = _cosign_registry_tag_name

    # Include manifest_b by tag name and manifest_a by digest.
    # From pulp/cosign-tags: manifest_b has a .sig companion and a V3 companion.
    # manifest_a has a .sig and .att companion.
    remote = container_remote_factory(
        upstream_name=PULP_COSIGN_COMPANION_TAGS,
        includes=["manifest_b", PULP_COSIGN_TAGS_MANIFEST_A_DIGEST],
    )
    repository = container_repository_factory()
    container_sync(repository, remote)
    ver = container_repository_api.read(repository.pulp_href).latest_version_href

    tags = container_tag_api.list(repository_version=ver)
    manifests = container_manifest_api.list(repository_version=ver)

    # manifest_b gets a tag (synced by tag name); manifest_a does not (synced by digest).
    # Cosign companions for both are pulled in as tagged content.
    assert {t.name for t in tags.results} == {
        "manifest_b",
        f"{cr(PULP_COSIGN_TAGS_MANIFEST_B_DIGEST)}.sig",
        cr(PULP_COSIGN_TAGS_MANIFEST_B_DIGEST),
        f"{cr(PULP_COSIGN_TAGS_MANIFEST_A_DIGEST)}.sig",
        f"{cr(PULP_COSIGN_TAGS_MANIFEST_A_DIGEST)}.att",
    }
    # manifest_a + manifest_b + b's .sig + b's V3 list + 2 V3 sub-manifests
    #   + a's .sig + a's .att  = 8
    assert manifests.count == 8

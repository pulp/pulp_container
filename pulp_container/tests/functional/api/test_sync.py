"""Tests that sync container plugin repositories."""

import pytest
from pulpcore.tests.functional.utils import PulpTaskError

from pulp_container.tests.functional.constants import PULP_FIXTURE_1, PULP_LABELED_FIXTURE

from pulp_container.tests.functional.constants import (
    REGISTRY_V2_FEED_URL,
)

# there is a manifest list and a listed manifest
BOOTABLE_MANIFESTS_COUNT = 2


@pytest.fixture
def synced_container_repository_factory(
    container_repository_factory, container_remote_factory, container_repository_api, container_sync
):
    def _synced_container_repository_factory(
        url=REGISTRY_V2_FEED_URL, include_tags=None, exclude_tags=None
    ):
        """Sync a new repository with the included tags passed as an argument."""
        remote = container_remote_factory(
            url,
            upstream_name=PULP_FIXTURE_1,
            include_tags=include_tags,
            exclude_tags=exclude_tags,
        )

        repository = container_repository_factory()

        container_sync(repository, remote)
        synced_repository = container_repository_api.read(repository.pulp_href)

        return synced_repository

    return _synced_container_repository_factory


@pytest.mark.parallel
def test_basic_sync(container_repo, container_remote, container_repository_api, container_sync):
    container_sync(container_repo, container_remote)
    repository = container_repository_api.read(container_repo.pulp_href)

    assert "versions/1/" in repository.latest_version_href

    latest_version_href = repository.latest_version_href
    container_sync(
        container_repo, container_remote
    )  # We expect that this second sync doesn't create a new repo version
    repository = container_repository_api.read(repository.pulp_href)

    assert repository.latest_version_href == latest_version_href


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
    with pytest.raises(PulpTaskError) as ctx:
        synced_container_repository_factory(url="http://i-am-an-invalid-url.com/invalid/")

    assert "[Name or service not known]" in ctx.value.task.error["description"]


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

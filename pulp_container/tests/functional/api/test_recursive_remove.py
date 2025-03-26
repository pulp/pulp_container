"""Tests that recursively remove container content from repositories."""

import pytest

from pulp_container.tests.functional.constants import PULP_FIXTURE_1, REGISTRY_V2_REPO_PULP


class TestRecursiveRemove:
    """
    Test recursively removing container content from a repository.

    This test targets the follow feature:
    https://pulp.plan.io/issues/5179
    """

    @pytest.fixture(scope="class")
    def setup(
        self,
        container_bindings,
        container_repository_factory,
        container_remote_factory,
        container_sync,
    ):
        """Sync pulp/test-fixture-1 so we can copy content from it."""
        repo = container_repository_factory()
        remote = container_remote_factory(upstream_name=PULP_FIXTURE_1)
        container_sync(repo, remote)
        from_repo = container_bindings.RepositoriesContainerApi.read(repo.pulp_href)
        latest_from_version = from_repo.latest_version_href
        return from_repo, latest_from_version

    def test_repository_only_no_latest_version(
        self, container_bindings, container_repo, monitor_task
    ):
        """Do not create a new version, when there is nothing to remove."""
        response = container_bindings.RepositoriesContainerApi.remove(container_repo.pulp_href, {})
        monitor_task(response.task)
        latest_version_href = container_bindings.RepositoriesContainerApi.read(
            container_repo.pulp_href
        ).latest_version_href
        assert latest_version_href == f"{container_repo.pulp_href}versions/0/"

    def test_remove_everything(self, container_bindings, container_repo, monitor_task, setup):
        """Remove everything from the repository.."""
        from_repo, latest_from_version = setup
        manifest_a = (
            container_bindings.ContentTagsApi.list(
                name="manifest_a", repository_version=latest_from_version
            )
            .results[0]
            .tagged_manifest
        )
        add_response = container_bindings.RepositoriesContainerApi.add(
            container_repo.pulp_href, {"content_units": [manifest_a]}
        )
        monitor_task(add_response.task)
        latest_version_href = container_bindings.RepositoriesContainerApi.read(
            container_repo.pulp_href
        ).latest_version_href
        latest = container_bindings.RepositoriesContainerVersionsApi.read(latest_version_href)

        # Ensure test begins in the correct state
        assert "container.tag" not in latest.content_summary.added
        assert latest.content_summary.added["container.manifest"]["count"] == 1
        assert latest.content_summary.added["container.blob"]["count"] == 3

        # Actual test
        remove_response = container_bindings.RepositoriesContainerApi.remove(
            container_repo.pulp_href, {"content_units": ["*"]}
        )
        monitor_task(remove_response.task)
        latest_version_href = container_bindings.RepositoriesContainerApi.read(
            container_repo.pulp_href
        ).latest_version_href
        latest = container_bindings.RepositoriesContainerVersionsApi.read(latest_version_href)
        assert latest.content_summary.present == {}
        assert latest.content_summary.removed["container.blob"]["count"] == 3
        assert latest.content_summary.removed["container.manifest"]["count"] == 1

    def test_remove_invalid_content_units(self, container_bindings, container_repo):
        """Ensure exception is raised when '*' is not the only item in the content_units."""
        with pytest.raises(container_bindings.ApiException) as context:
            container_bindings.RepositoriesContainerApi.remove(
                container_repo.pulp_href, {"content_units": ["*", "some_href"]}
            )
        assert context.value.status == 400

    def test_manifest_recursion(self, container_bindings, container_repo, monitor_task, setup):
        """Remove a manifest and its related blobs."""
        from_repo, latest_from_version = setup
        manifest_a = (
            container_bindings.ContentTagsApi.list(
                name="manifest_a", repository_version=latest_from_version
            )
            .results[0]
            .tagged_manifest
        )
        add_response = container_bindings.RepositoriesContainerApi.add(
            container_repo.pulp_href, {"content_units": [manifest_a]}
        )
        monitor_task(add_response.task)
        latest_version_href = container_bindings.RepositoriesContainerApi.read(
            container_repo.pulp_href
        ).latest_version_href
        latest = container_bindings.RepositoriesContainerVersionsApi.read(latest_version_href)

        # Ensure test begins in the correct state
        assert "container.tag" not in latest.content_summary.added
        assert latest.content_summary.added["container.manifest"]["count"] == 1
        assert latest.content_summary.added["container.blob"]["count"] == 3

        # Actual test
        remove_response = container_bindings.RepositoriesContainerApi.remove(
            container_repo.pulp_href, {"content_units": [manifest_a]}
        )
        monitor_task(remove_response.task)
        latest_version_href = container_bindings.RepositoriesContainerApi.read(
            container_repo.pulp_href
        ).latest_version_href
        latest = container_bindings.RepositoriesContainerVersionsApi.read(latest_version_href)
        assert "container.tag" not in latest.content_summary.removed
        assert latest.content_summary.removed["container.manifest"]["count"] == 1
        assert latest.content_summary.removed["container.blob"]["count"] == 3

    def test_manifest_list_recursion(self, container_bindings, container_repo, monitor_task, setup):
        """Remove a Manifest List, related manifests, and related blobs."""
        from_repo, latest_from_version = setup
        ml_i = (
            container_bindings.ContentTagsApi.list(
                name="ml_i", repository_version=latest_from_version
            )
            .results[0]
            .tagged_manifest
        )
        add_response = container_bindings.RepositoriesContainerApi.add(
            container_repo.pulp_href, {"content_units": [ml_i]}
        )
        monitor_task(add_response.task)
        latest_version_href = container_bindings.RepositoriesContainerApi.read(
            container_repo.pulp_href
        ).latest_version_href
        latest = container_bindings.RepositoriesContainerVersionsApi.read(latest_version_href)

        # Ensure test begins in the correct state
        assert "container.tag" not in latest.content_summary.added
        assert latest.content_summary.added["container.manifest"]["count"] == 3
        assert latest.content_summary.added["container.blob"]["count"] == 5

        # Actual test
        remove_response = container_bindings.RepositoriesContainerApi.remove(
            container_repo.pulp_href, {"content_units": [ml_i]}
        )
        monitor_task(remove_response.task)
        latest_version_href = container_bindings.RepositoriesContainerApi.read(
            container_repo.pulp_href
        ).latest_version_href
        latest = container_bindings.RepositoriesContainerVersionsApi.read(latest_version_href)
        assert "container.tag" not in latest.content_summary.removed
        assert latest.content_summary.removed["container.manifest"]["count"] == 3
        assert latest.content_summary.removed["container.blob"]["count"] == 5

    def test_tagged_manifest_list_recursion(
        self, container_bindings, container_repo, monitor_task, setup
    ):
        """Remove a tagged manifest list, and its related manifests and blobs."""
        from_repo, latest_from_version = setup
        ml_i_tag = (
            container_bindings.ContentTagsApi.list(
                name="ml_i", repository_version=latest_from_version
            )
            .results[0]
            .pulp_href
        )
        add_response = container_bindings.RepositoriesContainerApi.add(
            container_repo.pulp_href, {"content_units": [ml_i_tag]}
        )
        monitor_task(add_response.task)
        latest_version_href = container_bindings.RepositoriesContainerApi.read(
            container_repo.pulp_href
        ).latest_version_href
        latest = container_bindings.RepositoriesContainerVersionsApi.read(latest_version_href)

        # Ensure test begins in the correct state
        assert latest.content_summary.added["container.tag"]["count"] == 1
        assert latest.content_summary.added["container.manifest"]["count"] == 3
        assert latest.content_summary.added["container.blob"]["count"] == 5

        # Actual test
        remove_response = container_bindings.RepositoriesContainerApi.remove(
            container_repo.pulp_href, {"content_units": [ml_i_tag]}
        )
        monitor_task(remove_response.task)
        latest_version_href = container_bindings.RepositoriesContainerApi.read(
            container_repo.pulp_href
        ).latest_version_href
        latest = container_bindings.RepositoriesContainerVersionsApi.read(latest_version_href)
        assert latest.content_summary.removed["container.tag"]["count"] == 1
        assert latest.content_summary.removed["container.manifest"]["count"] == 3
        assert latest.content_summary.removed["container.blob"]["count"] == 5

    def test_tagged_manifest_recursion(
        self, container_bindings, container_repo, monitor_task, setup
    ):
        """Remove a tagged manifest and its related blobs."""
        from_repo, latest_from_version = setup
        manifest_a_tag = (
            container_bindings.ContentTagsApi.list(
                name="manifest_a", repository_version=latest_from_version
            )
            .results[0]
            .pulp_href
        )
        add_response = container_bindings.RepositoriesContainerApi.add(
            container_repo.pulp_href, {"content_units": [manifest_a_tag]}
        )
        monitor_task(add_response.task)
        latest_version_href = container_bindings.RepositoriesContainerApi.read(
            container_repo.pulp_href
        ).latest_version_href
        latest = container_bindings.RepositoriesContainerVersionsApi.read(latest_version_href)

        # Ensure valid starting state
        assert latest.content_summary.added["container.tag"]["count"] == 1
        assert latest.content_summary.added["container.manifest"]["count"] == 1
        assert latest.content_summary.added["container.blob"]["count"] == 3

        # Actual test
        remove_response = container_bindings.RepositoriesContainerApi.remove(
            container_repo.pulp_href, {"content_units": [manifest_a_tag]}
        )
        monitor_task(remove_response.task)
        latest_version_href = container_bindings.RepositoriesContainerApi.read(
            container_repo.pulp_href
        ).latest_version_href
        latest = container_bindings.RepositoriesContainerVersionsApi.read(latest_version_href)

        assert latest.content_summary.removed["container.tag"]["count"] == 1
        assert latest.content_summary.removed["container.manifest"]["count"] == 1
        assert latest.content_summary.removed["container.blob"]["count"] == 3

    def test_manifests_shared_blobs(self, container_bindings, container_repo, monitor_task, setup):
        """Starting with 2 manifests that share blobs, remove one of them."""
        from_repo, latest_from_version = setup
        manifest_a = (
            container_bindings.ContentTagsApi.list(
                name="manifest_a", repository_version=latest_from_version
            )
            .results[0]
            .tagged_manifest
        )
        manifest_e = (
            container_bindings.ContentTagsApi.list(
                name="manifest_e", repository_version=latest_from_version
            )
            .results[0]
            .tagged_manifest
        )
        add_response = container_bindings.RepositoriesContainerApi.add(
            container_repo.pulp_href, {"content_units": [manifest_a, manifest_e]}
        )
        monitor_task(add_response.task)
        latest_version_href = container_bindings.RepositoriesContainerApi.read(
            container_repo.pulp_href
        ).latest_version_href
        latest = container_bindings.RepositoriesContainerVersionsApi.read(latest_version_href)
        # Ensure valid starting state
        assert "container.tag" not in latest.content_summary.added
        assert latest.content_summary.added["container.manifest"]["count"] == 2
        # manifest_a has 2 blobs, 1 config blob, and manifest_e has 3 blobs 1 config blob
        # manifest_a blobs are shared with manifest_e
        assert latest.content_summary.added["container.blob"]["count"] == 5

        # Actual test
        remove_response = container_bindings.RepositoriesContainerApi.remove(
            container_repo.pulp_href, {"content_units": [manifest_e]}
        )
        monitor_task(remove_response.task)
        latest_version_href = container_bindings.RepositoriesContainerApi.read(
            container_repo.pulp_href
        ).latest_version_href
        latest = container_bindings.RepositoriesContainerVersionsApi.read(latest_version_href)
        assert "container.tag" not in latest.content_summary.removed
        assert latest.content_summary.removed["container.manifest"]["count"] == 1
        # Despite having 4 blobs, only 2 are removed, 2 is shared with manifest_a.
        assert latest.content_summary.removed["container.blob"]["count"] == 2

    def test_manifest_lists_shared_manifests(
        self, container_bindings, container_repo, monitor_task, setup
    ):
        """Starting with 2 manifest lists that share a manifest, remove one of them."""
        from_repo, latest_from_version = setup
        ml_i = (
            container_bindings.ContentTagsApi.list(
                name="ml_i", repository_version=latest_from_version
            )
            .results[0]
            .tagged_manifest
        )
        # Shares 1 manifest with ml_i
        ml_iii = (
            container_bindings.ContentTagsApi.list(
                name="ml_iii", repository_version=latest_from_version
            )
            .results[0]
            .tagged_manifest
        )
        add_response = container_bindings.RepositoriesContainerApi.add(
            container_repo.pulp_href, {"content_units": [ml_i, ml_iii]}
        )
        monitor_task(add_response.task)
        latest_version_href = container_bindings.RepositoriesContainerApi.read(
            container_repo.pulp_href
        ).latest_version_href
        latest = container_bindings.RepositoriesContainerVersionsApi.read(latest_version_href)
        # Ensure valid starting state
        assert "container.tag" not in latest.content_summary.added
        # 2 manifest lists, each with 2 manifests, 1 manifest shared
        assert latest.content_summary.added["container.manifest"]["count"] == 5
        assert latest.content_summary.added["container.blob"]["count"] == 7

        # Actual test
        remove_response = container_bindings.RepositoriesContainerApi.remove(
            container_repo.pulp_href, {"content_units": [ml_iii]}
        )
        monitor_task(remove_response.task)
        latest_version_href = container_bindings.RepositoriesContainerApi.read(
            container_repo.pulp_href
        ).latest_version_href
        latest = container_bindings.RepositoriesContainerVersionsApi.read(latest_version_href)
        assert "container.tag" not in latest.content_summary.removed
        # 1 manifest list, 1 manifest
        assert latest.content_summary.removed["container.manifest"]["count"] == 2
        assert latest.content_summary.removed["container.blob"]["count"] == 2

    def test_many_tagged_manifest_lists(
        self, container_bindings, container_repo, monitor_task, setup
    ):
        """Remove several Manifest List, related manifests, and related blobs."""
        from_repo, latest_from_version = setup
        ml_i_tag = (
            container_bindings.ContentTagsApi.list(
                name="ml_i", repository_version=latest_from_version
            )
            .results[0]
            .pulp_href
        )
        ml_ii_tag = (
            container_bindings.ContentTagsApi.list(
                name="ml_ii", repository_version=latest_from_version
            )
            .results[0]
            .pulp_href
        )
        ml_iii_tag = (
            container_bindings.ContentTagsApi.list(
                name="ml_iii", repository_version=latest_from_version
            )
            .results[0]
            .pulp_href
        )
        ml_iv_tag = (
            container_bindings.ContentTagsApi.list(
                name="ml_iv", repository_version=latest_from_version
            )
            .results[0]
            .pulp_href
        )
        add_response = container_bindings.RepositoriesContainerApi.add(
            container_repo.pulp_href,
            {"content_units": [ml_i_tag, ml_ii_tag, ml_iii_tag, ml_iv_tag]},
        )
        monitor_task(add_response.task)
        latest_version_href = container_bindings.RepositoriesContainerApi.read(
            container_repo.pulp_href
        ).latest_version_href
        latest = container_bindings.RepositoriesContainerVersionsApi.read(latest_version_href)

        assert latest.content_summary.added["container.tag"]["count"] == 4
        assert latest.content_summary.added["container.manifest"]["count"] == 9
        assert latest.content_summary.added["container.blob"]["count"] == 11

        remove_response = container_bindings.RepositoriesContainerApi.remove(
            container_repo.pulp_href,
            {"content_units": [ml_i_tag, ml_ii_tag, ml_iii_tag, ml_iv_tag]},
        )
        monitor_task(remove_response.task)
        latest_version_href = container_bindings.RepositoriesContainerApi.read(
            container_repo.pulp_href
        ).latest_version_href
        latest = container_bindings.RepositoriesContainerVersionsApi.read(latest_version_href)

        assert latest.content_summary.removed["container.tag"]["count"] == 4
        assert latest.content_summary.removed["container.manifest"]["count"] == 9
        assert latest.content_summary.removed["container.blob"]["count"] == 11

    def test_cannot_remove_tagged_manifest(
        self, container_bindings, container_repo, monitor_task, setup
    ):
        """
        Try to remove a manifest (without removing tag). Creates a new version, but nothing removed.
        """
        from_repo, latest_from_version = setup
        manifest_a_tag = container_bindings.ContentTagsApi.list(
            name="manifest_a", repository_version=latest_from_version
        ).results[0]
        add_response = container_bindings.RepositoriesContainerApi.add(
            container_repo.pulp_href, {"content_units": [manifest_a_tag.pulp_href]}
        )
        monitor_task(add_response.task)
        latest_version_href = container_bindings.RepositoriesContainerApi.read(
            container_repo.pulp_href
        ).latest_version_href
        latest = container_bindings.RepositoriesContainerVersionsApi.read(latest_version_href)
        assert latest.content_summary.added["container.tag"]["count"] == 1
        assert latest.content_summary.added["container.manifest"]["count"] == 1
        assert latest.content_summary.added["container.blob"]["count"] == 3

        remove_respone = container_bindings.RepositoriesContainerApi.remove(
            container_repo.pulp_href, {"content_units": [manifest_a_tag.tagged_manifest]}
        )
        monitor_task(remove_respone.task)

        latest_version_href = container_bindings.RepositoriesContainerApi.read(
            container_repo.pulp_href
        ).latest_version_href
        latest = container_bindings.RepositoriesContainerVersionsApi.read(latest_version_href)
        for content_type in ["container.tag", "container.manifest", "container.blob"]:
            assert content_type not in latest.content_summary.removed


def test_remove_image_push_repo(
    container_bindings, local_registry, registry_client, full_path, add_to_cleanup, monitor_task
):
    """Test the image removal within a push repository."""
    # the image tagged as 'manifest_a' consists of 3 blobs, 1 manifest, and 1 tag
    manifest_a_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    registry_client.pull(manifest_a_path)
    local_registry.tag_and_push(manifest_a_path, full_path("foo/bar:tag"))

    repo = container_bindings.RepositoriesContainerPushApi.list(name="foo/bar").results[0]
    distribution = container_bindings.DistributionsContainerApi.list(name="foo/bar").results[0]
    namespace = container_bindings.PulpContainerNamespacesApi.list(name="foo").results[0]
    add_to_cleanup(container_bindings.PulpContainerNamespacesApi, namespace.pulp_href)
    add_to_cleanup(container_bindings.DistributionsContainerApi, distribution.pulp_href)

    # create a new tag to test if all tags pointing to the same manifest will be removed
    tag = container_bindings.ContentTagsApi.list(
        name="tag", repository_version=repo.latest_version_href
    ).results[0]
    manifest_a = container_bindings.ContentManifestsApi.read(tag.tagged_manifest)
    tag_data = {"tag": "new_tag", "digest": manifest_a.digest}
    tag_response = container_bindings.RepositoriesContainerPushApi.tag(repo.pulp_href, tag_data)
    monitor_task(tag_response.task)

    repo = container_bindings.RepositoriesContainerPushApi.read(repo.pulp_href)
    latest_version_href = repo.latest_version_href
    content_to_remove = container_bindings.RepositoriesContainerPushVersionsApi.read(
        latest_version_href
    ).content_summary.present

    # Remove the 'manifest_a' image along with the related blobs, manifest, and tags.
    remove_response = container_bindings.RepositoriesContainerPushApi.remove_image(
        repo.pulp_href, {"digest": manifest_a.digest}
    )
    monitor_task(remove_response.task)

    latest_version_href = container_bindings.RepositoriesContainerPushApi.read(
        repo.pulp_href
    ).latest_version_href
    content_summary = container_bindings.RepositoriesContainerPushVersionsApi.read(
        latest_version_href
    ).content_summary

    assert content_summary.present == {}
    assert content_summary.added == {}

    assert (
        content_summary.removed["container.blob"]["count"]
        == content_to_remove["container.blob"]["count"]
    )
    assert (
        content_summary.removed["container.manifest"]["count"]
        == content_to_remove["container.manifest"]["count"]
    )
    assert (
        content_summary.removed["container.tag"]["count"]
        == content_to_remove["container.tag"]["count"]
    )

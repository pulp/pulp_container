"""Tests that recursively add container content to repositories."""

import pytest

from pulp_container.tests.functional.constants import PULP_FIXTURE_1
from pulp_container.constants import MEDIA_TYPE


class TestManifestCopy:
    """
    Test recursive copy of Manifests into a repository.

    This test targets the follow feature:
    https://pulp.plan.io/issues/3403
    """

    @pytest.fixture(scope="class")
    def from_repo(
        self,
        container_repository_factory,
        container_remote_factory,
        container_bindings,
        container_sync,
    ):
        """Sync pulp/test-fixture-1 so we can copy content from it."""
        repo = container_repository_factory()
        remote = container_remote_factory(upstream_name=PULP_FIXTURE_1)
        container_sync(repo, remote)
        return container_bindings.RepositoriesContainerApi.read(repo.pulp_href)

    @pytest.mark.parallel
    def test_missing_repository_argument(self, container_repo, container_bindings):
        """Ensure source_repository or source_repository_version is required."""
        with pytest.raises(container_bindings.ApiException) as exception:
            container_bindings.RepositoriesContainerApi.copy_manifests(container_repo.pulp_href, {})
        assert exception.value.status == 400

    @pytest.mark.parallel
    def test_source_repository_and_source_version(
        self, container_repo, container_bindings, from_repo
    ):
        """Passing source_repository_version and repository returns a 400."""
        with pytest.raises(container_bindings.ApiException) as context:
            container_bindings.RepositoriesContainerApi.copy_manifests(
                container_repo.pulp_href,
                {
                    "source_repository": from_repo.pulp_href,
                    "source_repository_version": from_repo.latest_version_href,
                },
            )
        assert context.value.status == 400

    @pytest.mark.parallel
    def test_copy_all_manifests(self, container_repo, container_bindings, monitor_task, from_repo):
        """Passing only source repository copies all manifests."""
        copy_response = container_bindings.RepositoriesContainerApi.copy_manifests(
            container_repo.pulp_href, {"source_repository": from_repo.pulp_href}
        )
        monitor_task(copy_response.task)

        latest_to = container_bindings.RepositoriesContainerApi.read(container_repo.pulp_href)
        latest_from = container_bindings.RepositoriesContainerApi.read(from_repo.pulp_href)
        to_repo_content = container_bindings.RepositoriesContainerVersionsApi.read(
            latest_to.latest_version_href
        ).content_summary.present
        from_repo_content = container_bindings.RepositoriesContainerVersionsApi.read(
            latest_from.latest_version_href
        ).content_summary.present
        for container_type in ["container.manifest", "container.blob"]:
            assert (
                to_repo_content[container_type]["count"]
                == from_repo_content[container_type]["count"]
            )
        assert "container.tag" not in to_repo_content

    @pytest.mark.parallel
    def test_copy_all_manifests_from_version(
        self, container_repo, container_bindings, monitor_task, from_repo
    ):
        """Passing only source version copies all manifests."""
        copy_response = container_bindings.RepositoriesContainerApi.copy_manifests(
            container_repo.pulp_href, {"source_repository_version": from_repo.latest_version_href}
        )
        monitor_task(copy_response.task)

        latest_to = container_bindings.RepositoriesContainerApi.read(container_repo.pulp_href)
        to_repo_content = container_bindings.RepositoriesContainerVersionsApi.read(
            latest_to.latest_version_href
        ).content_summary.present
        from_repo_content = container_bindings.RepositoriesContainerVersionsApi.read(
            from_repo.latest_version_href
        ).content_summary.present
        for container_type in ["container.manifest", "container.blob"]:
            assert (
                to_repo_content[container_type]["count"]
                == from_repo_content[container_type]["count"]
            )
        assert "container.tag" not in to_repo_content

    @pytest.mark.parallel
    def test_copy_manifest_by_digest(
        self, container_repo, container_bindings, monitor_task, from_repo
    ):
        """Specify a single manifest by digest to copy."""
        manifest_a_href = (
            container_bindings.ContentTagsApi.list(
                name="manifest_a", repository_version=from_repo.latest_version_href
            )
            .results[0]
            .tagged_manifest
        )
        manifest_a_digest = container_bindings.ContentManifestsApi.read(manifest_a_href).digest
        copy_response = container_bindings.RepositoriesContainerApi.copy_manifests(
            container_repo.pulp_href,
            {"source_repository": from_repo.pulp_href, "digests": [manifest_a_digest]},
        )
        monitor_task(copy_response.task)

        to_repo = container_bindings.RepositoriesContainerApi.read(container_repo.pulp_href)
        to_repo_content = container_bindings.RepositoriesContainerVersionsApi.read(
            to_repo.latest_version_href
        ).content_summary.present
        assert "container.tag" not in to_repo_content
        assert to_repo_content["container.manifest"]["count"] == 1
        # each manifest (non-list) has 3 blobs, 1 blob is shared
        assert to_repo_content["container.blob"]["count"] == 3

    @pytest.mark.parallel
    def test_copy_manifest_by_digest_and_media_type(
        self, container_repo, container_bindings, monitor_task, from_repo
    ):
        """Specify a single manifest by digest to copy."""
        manifest_a_href = (
            container_bindings.ContentTagsApi.list(
                name="manifest_a", repository_version=from_repo.latest_version_href
            )
            .results[0]
            .tagged_manifest
        )
        manifest_a_digest = container_bindings.ContentManifestsApi.read(manifest_a_href).digest
        copy_response = container_bindings.RepositoriesContainerApi.copy_manifests(
            container_repo.pulp_href,
            {
                "source_repository": from_repo.pulp_href,
                "digests": [manifest_a_digest],
                "media_types": [MEDIA_TYPE.MANIFEST_V2],
            },
        )
        monitor_task(copy_response.task)

        to_repo = container_bindings.RepositoriesContainerApi.read(container_repo.pulp_href)
        to_repo_content = container_bindings.RepositoriesContainerVersionsApi.read(
            to_repo.latest_version_href
        ).content_summary.present
        assert "container.tag" not in to_repo_content
        assert to_repo_content["container.manifest"]["count"] == 1
        # manifest_a has 3 blobs
        # 3rd blob is the parent blob from apline repo
        assert to_repo_content["container.blob"]["count"] == 3

    @pytest.mark.parallel
    def test_copy_all_manifest_lists_by_media_type(
        self, container_repo, container_bindings, monitor_task, from_repo
    ):
        """Specify the media_type, to copy all manifest lists."""
        copy_response = container_bindings.RepositoriesContainerApi.copy_manifests(
            container_repo.pulp_href,
            {
                "source_repository": from_repo.pulp_href,
                "media_types": [MEDIA_TYPE.MANIFEST_LIST],
            },
        )
        monitor_task(copy_response.task)

        to_repo = container_bindings.RepositoriesContainerApi.read(container_repo.pulp_href)
        to_repo_content = container_bindings.RepositoriesContainerVersionsApi.read(
            to_repo.latest_version_href
        ).content_summary.present
        assert "container.tag" not in to_repo_content
        # Fixture has 4 manifest lists, which combined reference 5 manifests
        assert to_repo_content["container.manifest"]["count"] == 9
        # each manifest (non-list) has 3 blobs, 1 blob is shared
        # 11th blob is the parent blob from apline repo, which is shared by all other manifests
        assert to_repo_content["container.blob"]["count"] == 11

    @pytest.mark.parallel
    def test_copy_all_manifests_by_media_type(
        self, container_repo, container_bindings, monitor_task, from_repo
    ):
        """Specify the media_type, to copy all manifest lists."""
        copy_response = container_bindings.RepositoriesContainerApi.copy_manifests(
            container_repo.pulp_href,
            {
                "source_repository": from_repo.pulp_href,
                "media_types": [MEDIA_TYPE.MANIFEST_V1, MEDIA_TYPE.MANIFEST_V2],
            },
        )
        monitor_task(copy_response.task)

        to_repo = container_bindings.RepositoriesContainerApi.read(container_repo.pulp_href)
        to_repo_content = container_bindings.RepositoriesContainerVersionsApi.read(
            to_repo.latest_version_href
        ).content_summary.present
        assert "container.tag" not in to_repo_content
        # Fixture has 5 manifests that aren't manifest lists
        assert to_repo_content["container.manifest"]["count"] == 5
        # each manifest (non-list) has 3 blobs, 1 blob is shared
        # 11th blob is the parent blob from apline repo, which is shared by all other manifests
        assert to_repo_content["container.blob"]["count"] == 11

    @pytest.mark.parallel
    def test_fail_to_copy_invalid_manifest_media_type(
        self, container_repo, container_bindings, from_repo, has_pulp_plugin
    ):
        """Specify the media_type, to copy all manifest lists."""
        # Pydantic addition to bindings in 3.70 prevents this test from working
        if has_pulp_plugin("core", max="3.70"):
            with pytest.raises(container_bindings.ApiException) as context:
                container_bindings.RepositoriesContainerApi.copy_manifests(
                    container_repo.pulp_href,
                    {
                        "source_repository": from_repo.pulp_href,
                        "media_types": ["wrongwrongwrong"],
                    },
                )
            assert context.value.status == 400

    @pytest.mark.parallel
    def test_copy_by_digest_with_incorrect_media_type(
        self, container_repo, container_bindings, monitor_task, from_repo
    ):
        """Ensure invalid media type will raise a 400."""
        ml_i_href = (
            container_bindings.ContentTagsApi.list(
                name="ml_i", repository_version=from_repo.latest_version_href
            )
            .results[0]
            .tagged_manifest
        )
        ml_i_digest = container_bindings.ContentManifestsApi.read(ml_i_href).digest

        copy_response = container_bindings.RepositoriesContainerApi.copy_manifests(
            container_repo.pulp_href,
            {
                "source_repository": from_repo.pulp_href,
                "digests": [ml_i_digest],
                "media_types": [MEDIA_TYPE.MANIFEST_V2],
            },
        )
        monitor_task(copy_response.task)

        latest_to_repo_href = container_bindings.RepositoriesContainerApi.read(
            container_repo.pulp_href
        ).latest_version_href
        # Assert no version created
        assert latest_to_repo_href == f"{container_repo.pulp_href}versions/0/"

    @pytest.mark.parallel
    def test_copy_multiple_manifests_by_digest(
        self, container_repo, container_bindings, monitor_task, from_repo
    ):
        """Specify digests to copy."""
        ml_i_href = (
            container_bindings.ContentTagsApi.list(
                name="ml_i", repository_version=from_repo.latest_version_href
            )
            .results[0]
            .tagged_manifest
        )
        ml_i_digest = container_bindings.ContentManifestsApi.read(ml_i_href).digest

        ml_ii_href = (
            container_bindings.ContentTagsApi.list(
                name="ml_ii", repository_version=from_repo.latest_version_href
            )
            .results[0]
            .tagged_manifest
        )
        ml_ii_digest = container_bindings.ContentManifestsApi.read(ml_ii_href).digest

        copy_response = container_bindings.RepositoriesContainerApi.copy_manifests(
            container_repo.pulp_href,
            {
                "source_repository": from_repo.pulp_href,
                "digests": [ml_i_digest, ml_ii_digest],
            },
        )
        monitor_task(copy_response.task)

        to_repo = container_bindings.RepositoriesContainerApi.read(container_repo.pulp_href)
        to_repo_content = container_bindings.RepositoriesContainerVersionsApi.read(
            to_repo.latest_version_href
        ).content_summary.present
        assert "container.tag" not in to_repo_content
        # each manifest list is a manifest and references 2 other manifests
        assert to_repo_content["container.manifest"]["count"] == 6
        # each manifest (non-list) has 3 blobs, 1 blob is shared
        # 9th blob is the parent blob from apline repo, which is shared by all other manifests
        assert to_repo_content["container.blob"]["count"] == 9

    @pytest.mark.parallel
    def test_copy_manifests_by_digest_empty_list(
        self, container_repo, container_bindings, from_repo
    ):
        """Passing an empty list copies no manifests."""
        container_bindings.RepositoriesContainerApi.copy_manifests(
            container_repo.pulp_href, {"source_repository": from_repo.pulp_href, "digests": []}
        )
        latest_to = container_bindings.RepositoriesContainerApi.read(container_repo.pulp_href)
        # Assert a new version was not created
        assert latest_to.latest_version_href == f"{container_repo.pulp_href}versions/0/"


class TestTagCopy:
    """Test recursive copy of tags content to a repository."""

    @pytest.fixture(scope="class")
    def from_repo(
        self,
        container_repository_factory,
        container_remote_factory,
        container_sync,
        container_bindings,
    ):
        """Sync pulp/test-fixture-1 so we can copy content from it."""
        remote = container_remote_factory(upstream_name=PULP_FIXTURE_1)
        repo = container_repository_factory()
        container_sync(repo, remote)
        return container_bindings.RepositoriesContainerApi.read(repo.pulp_href)

    @pytest.mark.parallel
    def test_missing_repository_argument(self, container_repo, container_bindings):
        """Ensure source_repository or source_repository_version is required."""
        with pytest.raises(container_bindings.ApiException):
            container_bindings.RepositoriesContainerApi.copy_tags(container_repo.pulp_href, {})

    @pytest.mark.parallel
    def test_source_repository_and_source_version(
        self, container_repo, container_bindings, from_repo
    ):
        """Passing both source_repository_version and source_repository returns a 400."""
        with pytest.raises(container_bindings.ApiException) as context:
            container_bindings.RepositoriesContainerApi.copy_tags(
                container_repo.pulp_href,
                {
                    "source_repository": from_repo.pulp_href,
                    "source_repository_version": from_repo.latest_version_href,
                },
            )
        assert context.value.status == 400

    @pytest.mark.parallel
    def test_copy_all_tags(self, container_repo, container_bindings, monitor_task, from_repo):
        """Passing only source and destination repositories copies all tags."""
        copy_response = container_bindings.RepositoriesContainerApi.copy_tags(
            container_repo.pulp_href, {"source_repository": from_repo.pulp_href}
        )
        monitor_task(copy_response.task)

        to_repo = container_bindings.RepositoriesContainerApi.read(container_repo.pulp_href)
        to_repo_content = container_bindings.RepositoriesContainerVersionsApi.read(
            to_repo.latest_version_href
        ).content_summary.present
        from_repo_content = container_bindings.RepositoriesContainerVersionsApi.read(
            from_repo.latest_version_href
        ).content_summary.present
        for container_type in ["container.tag", "container.manifest", "container.blob"]:
            assert (
                to_repo_content[container_type]["count"]
                == from_repo_content[container_type]["count"]
            )

    @pytest.mark.parallel
    def test_copy_all_tags_from_version(
        self, container_repo, container_bindings, monitor_task, from_repo
    ):
        """Passing only source version and destination repositories copies all tags."""
        latest_from_repo_href = from_repo.latest_version_href
        copy_response = container_bindings.RepositoriesContainerApi.copy_tags(
            container_repo.pulp_href, {"source_repository_version": latest_from_repo_href}
        )
        monitor_task(copy_response.task)

        to_repo = container_bindings.RepositoriesContainerApi.read(container_repo.pulp_href)
        to_repo_content = container_bindings.RepositoriesContainerVersionsApi.read(
            to_repo.latest_version_href
        ).content_summary.present
        from_repo_content = container_bindings.RepositoriesContainerVersionsApi.read(
            latest_from_repo_href
        ).content_summary.present
        for container_type in ["container.tag", "container.manifest", "container.blob"]:
            assert (
                to_repo_content[container_type]["count"]
                == from_repo_content[container_type]["count"]
            )

    @pytest.mark.parallel
    def test_copy_tags_by_name(self, container_repo, container_bindings, monitor_task, from_repo):
        """Copy tags in destination repo that match name."""
        copy_response = container_bindings.RepositoriesContainerApi.copy_tags(
            container_repo.pulp_href,
            {"source_repository": from_repo.pulp_href, "names": ["ml_i", "manifest_c"]},
        )
        monitor_task(copy_response.task)

        to_repo = container_bindings.RepositoriesContainerApi.read(container_repo.pulp_href)
        to_repo_content = container_bindings.RepositoriesContainerVersionsApi.read(
            to_repo.latest_version_href
        ).content_summary.present
        assert to_repo_content["container.tag"]["count"] == 2
        # ml_i has 1 manifest list, 2 manifests, manifest_c has 1 manifest
        assert to_repo_content["container.manifest"]["count"] == 4
        # each manifest (non-list) has 3 blobs, 1 blob is shared
        # 7th blob is the parent blob from apline repo, which is shared by all other manifests
        assert to_repo_content["container.blob"]["count"] == 7

    @pytest.mark.parallel
    def test_copy_tags_by_name_empty_list(
        self, container_repo, container_bindings, monitor_task, from_repo
    ):
        """Passing an empty list of names copies nothing."""
        copy_response = container_bindings.RepositoriesContainerApi.copy_tags(
            container_repo.pulp_href, {"source_repository": from_repo.pulp_href, "names": []}
        )
        monitor_task(copy_response.task)

        latest_to_repo_href = container_bindings.RepositoriesContainerApi.read(
            container_repo.pulp_href
        ).latest_version_href
        # Assert a new version was not created
        assert latest_to_repo_href == f"{container_repo.pulp_href}versions/0/"

    @pytest.mark.parallel
    def test_copy_tags_with_conflicting_names(
        self, container_repo, container_bindings, monitor_task, from_repo
    ):
        """If tag names are already present in a repository, the conflicting tags are removed."""
        copy_response = container_bindings.RepositoriesContainerApi.copy_tags(
            container_repo.pulp_href, {"source_repository": from_repo.pulp_href}
        )
        monitor_task(copy_response.task)
        # Tag the 'manifest_b' manifest as 'manifest_a'
        latest_version_href = container_bindings.RepositoriesContainerApi.read(
            container_repo.pulp_href
        ).latest_version_href
        manifest_b_href = (
            container_bindings.ContentTagsApi.list(
                name="manifest_b", repository_version=latest_version_href
            )
            .results[0]
            .tagged_manifest
        )
        manifest_b = container_bindings.ContentManifestsApi.read(manifest_b_href)
        params = {"tag": "manifest_a", "digest": manifest_b.digest}
        tag_response = container_bindings.RepositoriesContainerApi.tag(
            container_repo.pulp_href, params
        )
        monitor_task(tag_response.task)
        # Copy tags again from the original repo
        copy_response = container_bindings.RepositoriesContainerApi.copy_tags(
            container_repo.pulp_href, {"source_repository": from_repo.pulp_href}
        )
        monitor_task(copy_response.task)
        to_repo = container_bindings.RepositoriesContainerApi.read(container_repo.pulp_href)
        to_repo_content = container_bindings.RepositoriesContainerVersionsApi.read(
            to_repo.latest_version_href
        ).content_summary
        from_repo_content = container_bindings.RepositoriesContainerVersionsApi.read(
            from_repo.latest_version_href
        ).content_summary
        for container_type in ["container.tag", "container.manifest", "container.blob"]:
            assert (
                to_repo_content.present[container_type]["count"]
                == from_repo_content.present[container_type]["count"]
            )

        assert to_repo_content.added["container.tag"]["count"] == 1
        assert to_repo_content.removed["container.tag"]["count"] == 1


class TestRecursiveAdd:
    """Test recursively adding container content to a repository."""

    @pytest.fixture(scope="class")
    def from_repo(
        self,
        container_repository_factory,
        container_remote_factory,
        container_sync,
        container_bindings,
    ):
        """Sync pulp/test-fixture-1 so we can copy content from it."""
        repo = container_repository_factory()
        remote = container_remote_factory(upstream_name=PULP_FIXTURE_1)
        container_sync(repo, remote)
        return container_bindings.RepositoriesContainerApi.read(repo.pulp_href)

    @pytest.mark.parallel
    def test_repository_only(self, container_repo, container_bindings, monitor_task):
        """Passing only a repository does not create a new version."""
        add_response = container_bindings.RepositoriesContainerApi.add(container_repo.pulp_href, {})
        monitor_task(add_response.task)

        latest_version_href = container_bindings.RepositoriesContainerApi.read(
            container_repo.pulp_href
        ).latest_version_href
        assert latest_version_href == container_repo.latest_version_href

    @pytest.mark.parallel
    def test_manifest_recursion(self, container_repo, container_bindings, monitor_task, from_repo):
        """Add a manifest and its related blobs."""
        manifest_a = (
            container_bindings.ContentTagsApi.list(
                name="manifest_a", repository_version=from_repo.latest_version_href
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

        # No tags added
        assert "container.manifest-tag" not in latest.content_summary.added

        # each manifest (non-list) has 3 blobs, 1 blob is shared
        assert latest.content_summary.added["container.manifest"]["count"] == 1
        assert latest.content_summary.added["container.blob"]["count"] == 3

    @pytest.mark.parallel
    def test_manifest_list_recursion(
        self, container_repo, container_bindings, monitor_task, from_repo
    ):
        """Add a Manifest List, related manifests, and related blobs."""
        ml_i = (
            container_bindings.ContentTagsApi.list(
                name="ml_i", repository_version=from_repo.latest_version_href
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

        # No tags added
        assert "container.tag" not in latest.content_summary.added
        # 1 manifest list 2 manifests
        assert latest.content_summary.added["container.manifest"]["count"] == 3

    @pytest.mark.parallel
    def test_tagged_manifest_list_recursion(
        self, container_repo, container_bindings, monitor_task, from_repo
    ):
        """Add a tagged manifest list, and its related manifests and blobs."""
        ml_i_tag = (
            container_bindings.ContentTagsApi.list(
                name="ml_i", repository_version=from_repo.latest_version_href
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
        assert latest.content_summary.added["container.tag"]["count"] == 1
        # 1 manifest list 2 manifests
        assert latest.content_summary.added["container.manifest"]["count"] == 3
        # each manifest (non-list) has 3 blobs, 1 blob is shared
        # 5th blob is the parent blob from apline repo, which is shared by all other manifests
        assert latest.content_summary.added["container.blob"]["count"] == 5

    @pytest.mark.parallel
    def test_tagged_manifest_recursion(
        self, container_repo, container_bindings, monitor_task, from_repo
    ):
        """Add a tagged manifest and its related blobs."""
        manifest_a_tag = (
            container_bindings.ContentTagsApi.list(
                name="manifest_a", repository_version=from_repo.latest_version_href
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

        assert latest.content_summary.added["container.tag"]["count"] == 1
        assert latest.content_summary.added["container.manifest"]["count"] == 1
        assert latest.content_summary.added["container.blob"]["count"] == 3

    @pytest.mark.parallel
    def test_tag_replacement(self, container_repo, container_bindings, monitor_task, from_repo):
        """Add a tagged manifest to a repo with a tag of that name already in place."""
        manifest_a_tag = (
            container_bindings.ContentTagsApi.list(
                name="manifest_a", repository_version=from_repo.latest_version_href
            )
            .results[0]
            .pulp_href
        )

        # Add manifest_b to the repo
        manifest_b = (
            container_bindings.ContentTagsApi.list(
                name="manifest_b", repository_version=from_repo.latest_version_href
            )
            .results[0]
            .tagged_manifest
        )
        manifest_b_digest = container_bindings.ContentManifestsApi.read(manifest_b).digest
        add_response = container_bindings.RepositoriesContainerApi.add(
            container_repo.pulp_href, {"content_units": [manifest_b]}
        )
        monitor_task(add_response.task)
        # Tag manifest_b as `manifest_a`
        params = {"tag": "manifest_a", "digest": manifest_b_digest}
        container_bindings.RepositoriesContainerApi.tag(container_repo.pulp_href, params)

        # Now add original manifest_a tag to the repo, which should remove the
        # new manifest_a tag, but leave the tagged manifest (manifest_b)
        add_response = container_bindings.RepositoriesContainerApi.add(
            container_repo.pulp_href, {"content_units": [manifest_a_tag]}
        )
        monitor_task(add_response.task)

        latest_version_href = container_bindings.RepositoriesContainerApi.read(
            container_repo.pulp_href
        ).latest_version_href
        latest = container_bindings.RepositoriesContainerVersionsApi.read(latest_version_href)
        assert latest.content_summary.added["container.tag"]["count"] == 1
        assert latest.content_summary.removed["container.tag"]["count"] == 1
        assert "container.manifest" not in latest.content_summary.removed
        assert "container.blob" not in latest.content_summary.removed

    @pytest.mark.parallel
    def test_many_tagged_manifest_lists(
        self, container_repo, container_bindings, monitor_task, from_repo
    ):
        """Add several Manifest List, related manifests, and related blobs."""
        ml_i_tag = (
            container_bindings.ContentTagsApi.list(
                name="ml_i", repository_version=from_repo.latest_version_href
            )
            .results[0]
            .pulp_href
        )
        ml_ii_tag = (
            container_bindings.ContentTagsApi.list(
                name="ml_ii", repository_version=from_repo.latest_version_href
            )
            .results[0]
            .pulp_href
        )
        ml_iii_tag = (
            container_bindings.ContentTagsApi.list(
                name="ml_iii", repository_version=from_repo.latest_version_href
            )
            .results[0]
            .pulp_href
        )
        ml_iv_tag = (
            container_bindings.ContentTagsApi.list(
                name="ml_iv", repository_version=from_repo.latest_version_href
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

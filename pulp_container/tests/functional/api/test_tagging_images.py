"""Tests for tagging and untagging images."""

import pytest
import subprocess
from pulp_container.tests.functional.constants import (
    CONTAINER_TAG_PATH,
    PULP_FIXTURE_1,
    REGISTRY_V2_REPO_PULP,
)


@pytest.fixture
def tagger_helper(container_bindings, monitor_task):
    class TaggingTestCommons:
        """Common utilities for tagging and untagging images."""

        def __init__(self, repository):
            self.repository = repository

        def get_manifest_by_tag(self, tag_name):
            """Fetch a manifest by the tag name."""
            latest_version_href = container_bindings.RepositoriesContainerApi.read(
                self.repository.pulp_href
            ).latest_version_href

            manifest_href = (
                container_bindings.ContentTagsApi.list(
                    name=tag_name, repository_version=latest_version_href
                )
                .results[0]
                .tagged_manifest
            )
            return container_bindings.ContentManifestsApi.read(manifest_href)

        def tag_image(self, manifest, tag_name):
            """Perform a tagging operation."""
            tag_data = {"tag": tag_name, "digest": manifest.digest}
            tag_response = container_bindings.RepositoriesContainerApi.tag(
                self.repository.pulp_href, tag_data
            )
            monitor_task(tag_response.task)

        def untag_image(self, tag_name):
            """Perform an untagging operation."""
            untag_data = {"tag": tag_name}
            untag_response = container_bindings.RepositoriesContainerApi.untag(
                self.repository.pulp_href, untag_data
            )
            monitor_task(untag_response.task)

    return TaggingTestCommons


class RepositoryTaggingTestCase:
    """A test case for standard a container repository."""

    @pytest.fixture(scope="class", autouse=True)
    def setup(self, tagger_helper, container_repo, container_remote_factory, container_sync):
        """Create class wide-variables."""
        self.tagger = tagger_helper(container_repo)
        self.repository = container_repo

        remote = container_remote_factory(url=PULP_FIXTURE_1)
        container_sync(container_repo, remote)

    def test_01_tag_first_image(self, container_bindings):
        """
        Create a new test for manifest.

        This test checks if the tag was created in a new repository version.
        """
        manifest_a = self.tagger.get_manifest_by_tag("manifest_a")
        self.tagger.tag_image(manifest_a, "new_tag")

        new_repository_version_href = "{repository_href}versions/{new_version}/".format(
            repository_href=self.repository.pulp_href, new_version="2"
        )
        created_tag = container_bindings.ContentTagsApi.list(
            repository_version_added=new_repository_version_href
        ).results[0]
        assert created_tag.name == "new_tag"

        repository_version = container_bindings.RepositoriesContainerVersionsApi.read(
            new_repository_version_href
        )

        added_content = repository_version.content_summary.added
        added_tags = added_content["container.tag"]["count"]
        assert added_tags == 1

        removed_content = repository_version.content_summary.removed
        assert removed_content == {}

    def test_02_tag_first_image_with_same_tag(self, container_bindings):
        """
        Tag the same manifest with the same name.

        This test checks if a new repository version was created with no content added.
        """
        latest_version_before = container_bindings.RepositoriesContainerApi.read(
            self.repository.pulp_href
        ).latest_version_href

        manifest_a = self.tagger.get_manifest_by_tag("manifest_a")
        self.tagger.tag_image(manifest_a, "new_tag")

        latest_version_after = container_bindings.RepositoriesContainerApi.read(
            self.repository.pulp_href
        ).latest_version_href

        assert latest_version_before == latest_version_after

    def test_03_tag_second_image_with_same_tag(self, container_bindings):
        """
        Tag a different manifest with the same name.

        This test checks if a new repository version was created with a new content added
        and the old removed.
        """
        manifest_a = self.tagger.get_manifest_by_tag("manifest_a")
        manifest_b = self.tagger.get_manifest_by_tag("manifest_b")
        self.tagger.tag_image(manifest_b, "new_tag")

        new_repository_version_href = "{repository_href}versions/{new_version}/".format(
            repository_href=self.repository.pulp_href, new_version="3"
        )
        created_tag = container_bindings.ContentTagsApi.list(
            repository_version_added=new_repository_version_href
        ).results[0]
        assert created_tag.name == "new_tag"

        created_tag_manifest = container_bindings.ContentManifestsApi.read(
            created_tag.tagged_manifest
        )
        assert created_tag_manifest.digest == manifest_b.digest

        removed_tag = container_bindings.ContentTagsApi.list(
            repository_version_removed=new_repository_version_href
        ).results[0]
        assert removed_tag.name == "new_tag"

        removed_tag_manifest = container_bindings.ContentManifestsApi.read(
            removed_tag.tagged_manifest
        )
        assert removed_tag_manifest.digest == manifest_a.digest

        repository_version = container_bindings.RepositoriesContainerVersionsApi.read(
            new_repository_version_href
        )

        added_content = repository_version.content_summary.added
        added_tags = added_content["container.tag"]["count"]
        assert added_tags == 1

        removed_content = repository_version.content_summary.removed
        removed_tags = removed_content["container.tag"]["count"]
        assert removed_tags == 1

    def test_04_untag_second_image(self, container_bindings):
        """Untag the manifest and check if the tag was added in a new repository version."""
        self.tagger.untag_image("new_tag")

        new_repository_version_href = "{repository_href}versions/{new_version}/".format(
            repository_href=self.repository.pulp_href, new_version="4"
        )

        removed_tags_href = "{unit_path}?{filters}".format(
            unit_path=CONTAINER_TAG_PATH,
            filters=f"repository_version_removed={new_repository_version_href}",
        )

        repository_version = container_bindings.RepositoriesContainerVersionsApi.read(
            new_repository_version_href
        )

        removed_content = repository_version.content_summary.removed
        removed_tags = removed_content["container.tag"]["href"]
        assert removed_tags == removed_tags_href

        added_content = repository_version.content_summary.added
        assert added_content == {}

        removed_tag = container_bindings.ContentTagsApi.list(
            repository_version_removed=new_repository_version_href
        ).results[0]
        assert removed_tag.name == "new_tag"

    def test_05_untag_second_image_again(self, container_bindings):
        """Untag the manifest that was already untagged."""
        with pytest.raises(container_bindings.ApiException):
            self.tagger.untag_image("new_tag")


class PushRepositoryTaggingTestCase:
    """A test case for a container push repository."""

    @pytest.fixture(scope="class", autouse=True)
    def setup(self, tagger_helper, container_bindings, local_registry):
        """Define APIs to use and pull images needed later in tests."""
        self.repository_name = "namespace/tags"
        self.registry_repository_name = f"{local_registry.name}/{self.repository_name}"
        manifest_a = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
        tagged_registry_manifest_a = f"{self.registry_repository_name}:manifest_a"
        manifest_b = f"{REGISTRY_V2_REPO_PULP}:manifest_b"
        tagged_registry_manifest_b = f"{self.registry_repository_name}:manifest_b"

        local_registry.pull(manifest_a)
        local_registry.pull(manifest_b)
        local_registry.tag(manifest_a, tagged_registry_manifest_a)
        local_registry.tag(manifest_b, tagged_registry_manifest_b)
        local_registry.push(tagged_registry_manifest_a)
        local_registry.push(tagged_registry_manifest_b)

        self.repository = container_bindings.RepositoriesContainerPushApi.list(
            name=self.repository_name
        ).results[0]
        self.tagger = tagger_helper(self.repository)

    def test_01_tag_first_image(self, local_registry):
        """Check if a tag was created and correctly pulled from a repository."""
        manifest_a = self.tagger.get_manifest_by_tag("manifest_a")
        self.tagger.tag_image(manifest_a, "new_tag")

        tagged_image = f"{self.registry_repository_name}:new_tag"
        local_registry.pull(tagged_image)
        local_registry.rmi(tagged_image)

    def test_02_tag_second_image_with_same_tag(self, local_registry):
        """Check if the existing tag correctly references a new manifest."""
        tagged_image = f"{self.registry_repository_name}:manifest_b"
        local_registry.pull(tagged_image)
        local_image_b = local_registry.inspect(tagged_image)
        local_registry.rmi(tagged_image)

        manifest_b = self.tagger.get_manifest_by_tag("manifest_b")
        self.tagger.tag_image(manifest_b, "new_tag")
        tagged_image = f"{self.registry_repository_name}:new_tag"
        local_registry.pull(tagged_image)
        local_image_b_tagged = local_registry.inspect(tagged_image)

        assert local_image_b[0]["Id"] == local_image_b_tagged[0]["Id"]

        local_registry.rmi(tagged_image)

    def test_03_remove_tag(self, local_registry):
        """Check if the client cannot pull by the removed tag."""
        self.tagger.untag_image("new_tag")

        non_existing_tagged_image = f"{self.registry_repository_name}:new_tag"
        with pytest.raises(subprocess.CalledProcessError):
            local_registry.pull(non_existing_tagged_image)

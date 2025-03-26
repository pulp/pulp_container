"""Tests for tagging and untagging images."""

import pytest
import subprocess
from urllib.parse import urlparse
from pulp_container.tests.functional.constants import (
    PULP_FIXTURE_1,
    REGISTRY_V2_REPO_PULP,
)


@pytest.fixture(scope="class")
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


class TestRepositoryTagging:
    """A test case for standard a container repository."""

    @pytest.fixture(scope="class")
    def setup(
        self, tagger_helper, container_repository_factory, container_remote_factory, container_sync
    ):
        """Create class wide-variables."""
        repository = container_repository_factory()
        tagger = tagger_helper(repository)

        remote = container_remote_factory(upstream_name=PULP_FIXTURE_1)
        container_sync(repository, remote)
        return repository, tagger

    def test_01_tag_first_image(self, container_bindings, setup):
        """
        Create a new test for manifest.

        This test checks if the tag was created in a new repository version.
        """
        repository, tagger = setup
        manifest_a = tagger.get_manifest_by_tag("manifest_a")
        tagger.tag_image(manifest_a, "new_tag")

        new_repository_version_href = "{repository_href}versions/{new_version}/".format(
            repository_href=repository.pulp_href, new_version="2"
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

    def test_02_tag_first_image_with_same_tag(self, container_bindings, setup):
        """
        Tag the same manifest with the same name.

        This test checks if a new repository version was created with no content added.
        """
        repository, tagger = setup
        latest_version_before = container_bindings.RepositoriesContainerApi.read(
            repository.pulp_href
        ).latest_version_href

        manifest_a = tagger.get_manifest_by_tag("manifest_a")
        tagger.tag_image(manifest_a, "new_tag")

        latest_version_after = container_bindings.RepositoriesContainerApi.read(
            repository.pulp_href
        ).latest_version_href

        assert latest_version_before == latest_version_after

    def test_03_tag_second_image_with_same_tag(self, container_bindings, setup):
        """
        Tag a different manifest with the same name.

        This test checks if a new repository version was created with a new content added
        and the old removed.
        """
        repository, tagger = setup
        manifest_a = tagger.get_manifest_by_tag("manifest_a")
        manifest_b = tagger.get_manifest_by_tag("manifest_b")
        tagger.tag_image(manifest_b, "new_tag")

        new_repository_version_href = "{repository_href}versions/{new_version}/".format(
            repository_href=repository.pulp_href, new_version="3"
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

    def test_04_untag_second_image(self, container_bindings, setup):
        """Untag the manifest and check if the tag was added in a new repository version."""
        repository, tagger = setup
        tagger.untag_image("new_tag")

        new_repository_version_href = "{repository_href}versions/{new_version}/".format(
            repository_href=repository.pulp_href, new_version="4"
        )

        removed_tags_href = (
            f"/content/container/tags/?repository_version_removed={new_repository_version_href}"
        )

        repository_version = container_bindings.RepositoriesContainerVersionsApi.read(
            new_repository_version_href
        )

        removed_content = repository_version.content_summary.removed
        removed_tags = removed_content["container.tag"]["href"]
        assert removed_tags.endswith(removed_tags_href)

        added_content = repository_version.content_summary.added
        assert added_content == {}

        removed_tag = container_bindings.ContentTagsApi.list(
            repository_version_removed=new_repository_version_href
        ).results[0]
        assert removed_tag.name == "new_tag"

    def test_05_untag_second_image_again(self, container_bindings, setup):
        """Untag the manifest that was already untagged."""
        repository, tagger = setup
        with pytest.raises(container_bindings.ApiException):
            tagger.untag_image("new_tag")


class TestPushRepositoryTagging:
    """A test case for a container push repository."""

    repository_name = "namespace/tags"

    @pytest.fixture(scope="class")
    def setup(self, tagger_helper, container_bindings, registry_client, full_path, add_to_cleanup):
        """Define APIs to use and pull images needed later in tests."""
        cfg = container_bindings.client.configuration
        registry_name = urlparse(cfg.host).netloc
        registry_repository_name = f"{registry_name}/{full_path(self.repository_name)}"
        manifest_a = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
        tagged_registry_manifest_a = f"{registry_repository_name}:manifest_a"
        manifest_b = f"{REGISTRY_V2_REPO_PULP}:manifest_b"
        tagged_registry_manifest_b = f"{registry_repository_name}:manifest_b"

        registry_client.pull(manifest_a)
        registry_client.pull(manifest_b)
        registry_client.tag(manifest_a, tagged_registry_manifest_a)
        registry_client.tag(manifest_b, tagged_registry_manifest_b)
        registry_client.login("-u", cfg.username, "-p", cfg.password, registry_name)
        registry_client.push(tagged_registry_manifest_a)
        registry_client.push(tagged_registry_manifest_b)
        registry_client.logout(registry_name)

        repository = container_bindings.RepositoriesContainerPushApi.list(
            name=self.repository_name
        ).results[0]
        tagger = tagger_helper(repository)
        distro = container_bindings.DistributionsContainerApi.list(
            name=self.repository_name
        ).results[0]
        add_to_cleanup(container_bindings.DistributionsContainerApi, distro.pulp_href)
        return repository, tagger

    def test_01_tag_first_image(self, local_registry, setup, full_path):
        """Check if a tag was created and correctly pulled from a repository."""
        repository, tagger = setup
        manifest_a = tagger.get_manifest_by_tag("manifest_a")
        tagger.tag_image(manifest_a, "new_tag")

        tagged_image = full_path(f"{self.repository_name}:new_tag")
        local_registry.pull(tagged_image)
        local_registry._dispatch_command("rmi", tagged_image)

    def test_02_tag_second_image_with_same_tag(self, local_registry, setup, full_path):
        """Check if the existing tag correctly references a new manifest."""
        repository, tagger = setup
        tagged_image = full_path(f"{self.repository_name}:manifest_b")
        local_registry.pull(tagged_image)
        local_image_b = local_registry.inspect(tagged_image)
        local_registry._dispatch_command("rmi", tagged_image)

        manifest_b = tagger.get_manifest_by_tag("manifest_b")
        tagger.tag_image(manifest_b, "new_tag")
        tagged_image = full_path(f"{self.repository_name}:new_tag")
        local_registry.pull(tagged_image)
        local_image_b_tagged = local_registry.inspect(tagged_image)

        assert local_image_b[0]["Id"] == local_image_b_tagged[0]["Id"]

        local_registry._dispatch_command("rmi", tagged_image)

    def test_03_remove_tag(self, local_registry, setup, full_path):
        """Check if the client cannot pull by the removed tag."""
        repository, tagger = setup
        tagger.untag_image("new_tag")

        non_existing_tagged_image = full_path(f"{self.repository_name}:new_tag")
        with pytest.raises(subprocess.CalledProcessError):
            local_registry.pull(non_existing_tagged_image)

# coding=utf-8
"""Tests for tagging and untagging images."""
import unittest

from urllib.parse import urlparse

from pulp_smash import cli, config, exceptions
from pulp_smash.pulp3.bindings import monitor_task
from pulp_smash.pulp3.utils import delete_orphans, gen_repo

from pulp_container.tests.functional.utils import (
    gen_container_remote,
    gen_container_client,
)
from pulp_container.tests.functional.constants import (
    CONTAINER_TAG_PATH,
    DOCKERHUB_PULP_FIXTURE_1,
)

from pulpcore.client.pulp_container import (
    ApiException,
    ContainerContainerRemote,
    ContainerContainerRepository,
    ContentManifestsApi,
    ContentTagsApi,
    RepositoriesContainerApi,
    RepositoriesContainerPushApi,
    RepositoriesContainerVersionsApi,
    RepositorySyncURL,
    RemotesContainerApi,
    TagImage,
    UnTagImage,
)


class TaggingTestCommons:
    """Common utilities for tagging and untagging images."""

    def get_manifest_by_tag(self, tag_name):
        """Fetch a manifest by the tag name."""
        latest_version_href = self.repositories_api.read(
            self.repository.pulp_href
        ).latest_version_href

        manifest_href = (
            self.tags_api.list(name=tag_name, repository_version=latest_version_href)
            .results[0]
            .tagged_manifest
        )
        return self.manifests_api.read(manifest_href)

    def tag_image(self, manifest, tag_name):
        """Perform a tagging operation."""
        tag_data = TagImage(tag=tag_name, digest=manifest.digest)
        tag_response = self.repositories_api.tag(self.repository.pulp_href, tag_data)
        monitor_task(tag_response.task)

    def untag_image(self, tag_name):
        """Perform an untagging operation."""
        untag_data = UnTagImage(tag=tag_name)
        untag_response = self.repositories_api.untag(self.repository.pulp_href, untag_data)
        monitor_task(untag_response.task)


class RepositoryTaggingTestCase(TaggingTestCommons, unittest.TestCase):
    """A test case for standard a container repository."""

    @classmethod
    def setUpClass(cls):
        """Create class wide-variables."""
        api_client = gen_container_client()
        cls.repositories_api = RepositoriesContainerApi(api_client)
        cls.versions_api = RepositoriesContainerVersionsApi(api_client)
        cls.remotes_api = RemotesContainerApi(api_client)
        cls.tags_api = ContentTagsApi(api_client)
        cls.manifests_api = ContentManifestsApi(api_client)

        cls.repository = cls.repositories_api.create(ContainerContainerRepository(**gen_repo()))

        remote_data = gen_container_remote(upstream_name=DOCKERHUB_PULP_FIXTURE_1)
        cls.remote = cls.remotes_api.create(ContainerContainerRemote(**remote_data))

        sync_data = RepositorySyncURL(remote=cls.remote.pulp_href)
        sync_response = cls.repositories_api.sync(cls.repository.pulp_href, sync_data)
        monitor_task(sync_response.task)

    @classmethod
    def tearDownClass(cls):
        """Clean generated resources."""
        cls.repositories_api.delete(cls.repository.pulp_href)
        cls.remotes_api.delete(cls.remote.pulp_href)
        delete_orphans()

    def test_01_tag_first_image(self):
        """
        Create a new test for manifest.

        This test checks if the tag was created in a new repository version.
        """
        manifest_a = self.get_manifest_by_tag("manifest_a")
        self.tag_image(manifest_a, "new_tag")

        new_repository_version_href = "{repository_href}versions/{new_version}/".format(
            repository_href=self.repository.pulp_href, new_version="2"
        )
        created_tag = self.tags_api.list(
            repository_version_added=new_repository_version_href
        ).results[0]
        self.assertEqual(created_tag.name, "new_tag")

        repository_version = self.versions_api.read(new_repository_version_href)

        added_content = repository_version.content_summary.added
        added_tags = added_content["container.tag"]["count"]
        self.assertEqual(added_tags, 1)

        removed_content = repository_version.content_summary.removed
        self.assertEqual(removed_content, {})

    def test_02_tag_first_image_with_same_tag(self):
        """
        Tag the same manifest with the same name.

        This test checks if a new repository version was created with no content added.
        """
        latest_version_before = self.repositories_api.read(
            self.repository.pulp_href
        ).latest_version_href

        manifest_a = self.get_manifest_by_tag("manifest_a")
        self.tag_image(manifest_a, "new_tag")

        latest_version_after = self.repositories_api.read(
            self.repository.pulp_href
        ).latest_version_href

        self.assertEqual(latest_version_before, latest_version_after)

    def test_03_tag_second_image_with_same_tag(self):
        """
        Tag a different manifest with the same name.

        This test checks if a new repository version was created with a new content added
        and the old removed.
        """
        manifest_a = self.get_manifest_by_tag("manifest_a")
        manifest_b = self.get_manifest_by_tag("manifest_b")
        self.tag_image(manifest_b, "new_tag")

        new_repository_version_href = "{repository_href}versions/{new_version}/".format(
            repository_href=self.repository.pulp_href, new_version="3"
        )
        created_tag = self.tags_api.list(
            repository_version_added=new_repository_version_href
        ).results[0]
        self.assertEqual(created_tag.name, "new_tag")

        created_tag_manifest = self.manifests_api.read(created_tag.tagged_manifest)
        self.assertEqual(created_tag_manifest, manifest_b)

        removed_tag = self.tags_api.list(
            repository_version_removed=new_repository_version_href
        ).results[0]
        self.assertEqual(removed_tag.name, "new_tag")

        removed_tag_manifest = self.manifests_api.read(removed_tag.tagged_manifest)
        self.assertEqual(removed_tag_manifest, manifest_a)

        repository_version = self.versions_api.read(new_repository_version_href)

        added_content = repository_version.content_summary.added
        added_tags = added_content["container.tag"]["count"]
        self.assertEqual(added_tags, 1)

        removed_content = repository_version.content_summary.removed
        removed_tags = removed_content["container.tag"]["count"]
        self.assertEqual(removed_tags, 1)

    def test_04_untag_second_image(self):
        """Untag the manifest and check if the tag was added in a new repository version."""
        self.untag_image("new_tag")

        new_repository_version_href = "{repository_href}versions/{new_version}/".format(
            repository_href=self.repository.pulp_href, new_version="4"
        )

        removed_tags_href = "{unit_path}?{filters}".format(
            unit_path=CONTAINER_TAG_PATH,
            filters=f"repository_version_removed={new_repository_version_href}",
        )

        repository_version = self.versions_api.read(new_repository_version_href)

        removed_content = repository_version.content_summary.removed
        removed_tags = removed_content["container.tag"]["href"]
        self.assertEqual(removed_tags, removed_tags_href)

        added_content = repository_version.content_summary.added
        self.assertEqual(added_content, {})

        removed_tag = self.tags_api.list(
            repository_version_removed=new_repository_version_href
        ).results[0]
        self.assertEqual(removed_tag.name, "new_tag")

    def test_05_untag_second_image_again(self):
        """Untag the manifest that was already untagged."""
        with self.assertRaises(ApiException):
            self.untag_image("new_tag")


class PushRepositoryTaggingTestCase(TaggingTestCommons, unittest.TestCase):
    """A test case for a container push repository."""

    @classmethod
    def setUpClass(cls):
        """Define APIs to use and pull images needed later in tests."""
        api_client = gen_container_client()
        cls.tags_api = ContentTagsApi(api_client)
        cls.manifests_api = ContentManifestsApi(api_client)
        cls.repositories_api = RepositoriesContainerPushApi(api_client)

        cfg = config.get_config()
        cls.registry = cli.RegistryClient(cfg)
        cls.registry.raise_if_unsupported(unittest.SkipTest, "Tests require podman/docker")
        cls.registry_name = urlparse(cfg.get_base_url()).netloc

        cls.repository_name = "namespace/tags"
        cls.registry_repository_name = f"{cls.registry_name}/{cls.repository_name}"
        manifest_a = f"{DOCKERHUB_PULP_FIXTURE_1}:manifest_a"
        tagged_registry_manifest_a = f"{cls.registry_repository_name}:manifest_a"
        manifest_b = f"{DOCKERHUB_PULP_FIXTURE_1}:manifest_b"
        tagged_registry_manifest_b = f"{cls.registry_repository_name}:manifest_b"

        cls.registry.pull(manifest_a)
        cls.registry.pull(manifest_b)
        cls.registry.tag(manifest_a, tagged_registry_manifest_a)
        cls.registry.tag(manifest_b, tagged_registry_manifest_b)
        cls.registry.login("-u", "admin", "-p", "password", cls.registry_name)
        cls.registry.push(tagged_registry_manifest_a)
        cls.registry.push(tagged_registry_manifest_b)

        cls.repository = cls.repositories_api.list(name=cls.repository_name).results[0]

    def test_01_tag_first_image(self):
        """Check if a tag was created and correctly pulled from a repository."""
        manifest_a = self.get_manifest_by_tag("manifest_a")
        self.tag_image(manifest_a, "new_tag")

        tagged_image = f"{self.registry_repository_name}:new_tag"
        self.registry.pull(tagged_image)
        self.registry.rmi(tagged_image)

    def test_02_tag_second_image_with_same_tag(self):
        """Check if the existing tag correctly references a new manifest."""
        tagged_image = f"{self.registry_repository_name}:manifest_b"
        self.registry.pull(tagged_image)
        local_image_b = self.registry.inspect(tagged_image)
        self.registry.rmi(tagged_image)

        manifest_b = self.get_manifest_by_tag("manifest_b")
        self.tag_image(manifest_b, "new_tag")
        tagged_image = f"{self.registry_repository_name}:new_tag"
        self.registry.pull(tagged_image)
        local_image_b_tagged = self.registry.inspect(tagged_image)

        self.assertEqual(local_image_b[0]["Id"], local_image_b_tagged[0]["Id"])

        self.registry.rmi(tagged_image)

    def test_03_remove_tag(self):
        """Check if the client cannot pull by the removed tag."""
        self.untag_image("new_tag")

        non_existing_tagged_image = f"{self.registry_repository_name}:new_tag"
        with self.assertRaises(exceptions.CalledProcessError):
            self.registry.pull(non_existing_tagged_image)

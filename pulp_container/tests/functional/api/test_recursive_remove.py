# # coding=utf-8
"""Tests that recursively remove container content from repositories."""
import unittest

from urllib.parse import urlparse

from pulp_smash import cli, config
from pulp_smash.pulp3.bindings import (
    delete_orphans,
    monitor_task,
    PulpTestCase,
)
from pulp_smash.pulp3.utils import gen_repo

from pulp_container.tests.functional.api import rbac_base
from pulp_container.tests.functional.utils import (
    gen_container_remote,
    gen_container_client,
)
from pulp_container.tests.functional.constants import PULP_FIXTURE_1, REGISTRY_V2_REPO_PULP

from pulpcore.client.pulp_container import (
    ApiException,
    ContainerContainerRemote,
    ContainerContainerRepository,
    ContentManifestsApi,
    ContentTagsApi,
    DistributionsContainerApi,
    PulpContainerNamespacesApi,
    RemoveImage,
    RemotesContainerApi,
    RepositoriesContainerApi,
    RepositoriesContainerPushApi,
    RepositoriesContainerVersionsApi,
    RepositorySyncURL,
    TagImage,
)


class TestRecursiveRemove(PulpTestCase):
    """
    Test recursively removing container content from a repository.

    This test targets the follow feature:
    https://pulp.plan.io/issues/5179
    """

    @classmethod
    def setUpClass(cls):
        """Sync pulp/test-fixture-1 so we can copy content from it."""
        api_client = gen_container_client()
        cls.repositories_api = RepositoriesContainerApi(api_client)
        cls.remotes_api = RemotesContainerApi(api_client)
        cls.tags_api = ContentTagsApi(api_client)
        cls.versions_api = RepositoriesContainerVersionsApi(api_client)

        cls.from_repo = cls.repositories_api.create(ContainerContainerRepository(**gen_repo()))

        remote_data = gen_container_remote(upstream_name=PULP_FIXTURE_1)
        cls.remote = cls.remotes_api.create(ContainerContainerRemote(**remote_data))

        sync_data = RepositorySyncURL(remote=cls.remote.pulp_href)
        sync_response = cls.repositories_api.sync(cls.from_repo.pulp_href, sync_data)
        monitor_task(sync_response.task)

        cls.latest_from_version = cls.repositories_api.read(
            cls.from_repo.pulp_href
        ).latest_version_href

    def setUp(self):
        """Create an empty repository to copy into."""
        self.to_repo = self.repositories_api.create(ContainerContainerRepository(**gen_repo()))
        self.addCleanup(self.repositories_api.delete, self.to_repo.pulp_href)

    @classmethod
    def tearDownClass(cls):
        """Delete things made in setUpClass. addCleanup feature does not work with setupClass."""
        cls.repositories_api.delete(cls.from_repo.pulp_href)
        cls.remotes_api.delete(cls.remote.pulp_href)
        delete_orphans()

    def test_repository_only_no_latest_version(self):
        """Do not create a new version, when there is nothing to remove."""
        self.repositories_api.remove(self.to_repo.pulp_href, {})
        latest_version_href = self.repositories_api.read(self.to_repo.pulp_href).latest_version_href
        self.assertEqual(latest_version_href, f"{self.to_repo.pulp_href}versions/0/")

    def test_remove_everything(self):
        """Add a manifest and its related blobs."""
        manifest_a = (
            self.tags_api.list(name="manifest_a", repository_version=self.latest_from_version)
            .results[0]
            .tagged_manifest
        )
        add_response = self.repositories_api.add(
            self.to_repo.pulp_href, {"content_units": [manifest_a]}
        )
        monitor_task(add_response.task)
        latest_version_href = self.repositories_api.read(self.to_repo.pulp_href).latest_version_href
        latest = self.versions_api.read(latest_version_href)

        # Ensure test begins in the correct state
        self.assertFalse("container.tag" in latest.content_summary.added)
        self.assertEqual(latest.content_summary.added["container.manifest"]["count"], 1)
        self.assertEqual(latest.content_summary.added["container.blob"]["count"], 3)

        # Actual test
        remove_response = self.repositories_api.remove(
            self.to_repo.pulp_href, {"content_units": ["*"]}
        )
        monitor_task(remove_response.task)
        latest_version_href = self.repositories_api.read(self.to_repo.pulp_href).latest_version_href
        latest = self.versions_api.read(latest_version_href)
        self.assertEqual(latest.content_summary.present, {})
        self.assertEqual(latest.content_summary.removed["container.blob"]["count"], 3)
        self.assertEqual(latest.content_summary.removed["container.manifest"]["count"], 1)

    def test_remove_invalid_content_units(self):
        """Ensure exception is raised when '*' is not the only item in the content_units."""
        with self.assertRaises(ApiException) as context:
            self.repositories_api.remove(
                self.to_repo.pulp_href, {"content_units": ["*", "some_href"]}
            )
        self.assertEqual(context.exception.status, 400)

    def test_manifest_recursion(self):
        """Add a manifest and its related blobs."""
        manifest_a = (
            self.tags_api.list(name="manifest_a", repository_version=self.latest_from_version)
            .results[0]
            .tagged_manifest
        )
        add_response = self.repositories_api.add(
            self.to_repo.pulp_href, {"content_units": [manifest_a]}
        )
        monitor_task(add_response.task)
        latest_version_href = self.repositories_api.read(self.to_repo.pulp_href).latest_version_href
        latest = self.versions_api.read(latest_version_href)

        # Ensure test begins in the correct state
        self.assertFalse("container.tag" in latest.content_summary.added)
        self.assertEqual(latest.content_summary.added["container.manifest"]["count"], 1)
        self.assertEqual(latest.content_summary.added["container.blob"]["count"], 3)

        # Actual test
        remove_response = self.repositories_api.remove(
            self.to_repo.pulp_href, {"content_units": [manifest_a]}
        )
        monitor_task(remove_response.task)
        latest_version_href = self.repositories_api.read(self.to_repo.pulp_href).latest_version_href
        latest = self.versions_api.read(latest_version_href)
        self.assertFalse("container.tag" in latest.content_summary.removed)
        self.assertEqual(latest.content_summary.removed["container.manifest"]["count"], 1)
        self.assertEqual(latest.content_summary.removed["container.blob"]["count"], 3)

    def test_manifest_list_recursion(self):
        """Add a Manifest List, related manifests, and related blobs."""
        ml_i = (
            self.tags_api.list(name="ml_i", repository_version=self.latest_from_version)
            .results[0]
            .tagged_manifest
        )
        add_response = self.repositories_api.add(self.to_repo.pulp_href, {"content_units": [ml_i]})
        monitor_task(add_response.task)
        latest_version_href = self.repositories_api.read(self.to_repo.pulp_href).latest_version_href
        latest = self.versions_api.read(latest_version_href)

        # Ensure test begins in the correct state
        self.assertFalse("container.tag" in latest.content_summary.added)
        self.assertEqual(latest.content_summary.added["container.manifest"]["count"], 3)
        self.assertEqual(latest.content_summary.added["container.blob"]["count"], 5)

        # Actual test
        remove_response = self.repositories_api.remove(
            self.to_repo.pulp_href, {"content_units": [ml_i]}
        )
        monitor_task(remove_response.task)
        latest_version_href = self.repositories_api.read(self.to_repo.pulp_href).latest_version_href
        latest = self.versions_api.read(latest_version_href)
        self.assertFalse("container.tag" in latest.content_summary.removed)
        self.assertEqual(latest.content_summary.removed["container.manifest"]["count"], 3)
        self.assertEqual(latest.content_summary.removed["container.blob"]["count"], 5)

    def test_tagged_manifest_list_recursion(self):
        """Add a tagged manifest list, and its related manifests and blobs."""
        ml_i_tag = (
            self.tags_api.list(name="ml_i", repository_version=self.latest_from_version)
            .results[0]
            .pulp_href
        )
        add_response = self.repositories_api.add(
            self.to_repo.pulp_href, {"content_units": [ml_i_tag]}
        )
        monitor_task(add_response.task)
        latest_version_href = self.repositories_api.read(self.to_repo.pulp_href).latest_version_href
        latest = self.versions_api.read(latest_version_href)

        # Ensure test begins in the correct state
        self.assertEqual(latest.content_summary.added["container.tag"]["count"], 1)
        self.assertEqual(latest.content_summary.added["container.manifest"]["count"], 3)
        self.assertEqual(latest.content_summary.added["container.blob"]["count"], 5)

        # Actual test
        remove_response = self.repositories_api.remove(
            self.to_repo.pulp_href, {"content_units": [ml_i_tag]}
        )
        monitor_task(remove_response.task)
        latest_version_href = self.repositories_api.read(self.to_repo.pulp_href).latest_version_href
        latest = self.versions_api.read(latest_version_href)
        self.assertEqual(latest.content_summary.removed["container.tag"]["count"], 1)
        self.assertEqual(latest.content_summary.removed["container.manifest"]["count"], 3)
        self.assertEqual(latest.content_summary.removed["container.blob"]["count"], 5)

    def test_tagged_manifest_recursion(self):
        """Add a tagged manifest and its related blobs."""
        manifest_a_tag = (
            self.tags_api.list(name="manifest_a", repository_version=self.latest_from_version)
            .results[0]
            .pulp_href
        )
        add_response = self.repositories_api.add(
            self.to_repo.pulp_href, {"content_units": [manifest_a_tag]}
        )
        monitor_task(add_response.task)
        latest_version_href = self.repositories_api.read(self.to_repo.pulp_href).latest_version_href
        latest = self.versions_api.read(latest_version_href)

        # Ensure valid starting state
        self.assertEqual(latest.content_summary.added["container.tag"]["count"], 1)
        self.assertEqual(latest.content_summary.added["container.manifest"]["count"], 1)
        self.assertEqual(latest.content_summary.added["container.blob"]["count"], 3)

        # Actual test
        remove_response = self.repositories_api.remove(
            self.to_repo.pulp_href, {"content_units": [manifest_a_tag]}
        )
        monitor_task(remove_response.task)
        latest_version_href = self.repositories_api.read(self.to_repo.pulp_href).latest_version_href
        latest = self.versions_api.read(latest_version_href)

        self.assertEqual(latest.content_summary.removed["container.tag"]["count"], 1)
        self.assertEqual(latest.content_summary.removed["container.manifest"]["count"], 1)
        self.assertEqual(latest.content_summary.removed["container.blob"]["count"], 3)

    def test_manifests_shared_blobs(self):
        """Starting with 2 manifests that share blobs, remove one of them."""
        manifest_a = (
            self.tags_api.list(name="manifest_a", repository_version=self.latest_from_version)
            .results[0]
            .tagged_manifest
        )
        manifest_e = (
            self.tags_api.list(name="manifest_e", repository_version=self.latest_from_version)
            .results[0]
            .tagged_manifest
        )
        add_response = self.repositories_api.add(
            self.to_repo.pulp_href, {"content_units": [manifest_a, manifest_e]}
        )
        monitor_task(add_response.task)
        latest_version_href = self.repositories_api.read(self.to_repo.pulp_href).latest_version_href
        latest = self.versions_api.read(latest_version_href)
        # Ensure valid starting state
        self.assertFalse("container.tag" in latest.content_summary.added)
        self.assertEqual(latest.content_summary.added["container.manifest"]["count"], 2)
        # manifest_a has 2 blobs, 1 config blob, and manifest_e has 3 blobs 1 config blob
        # manifest_a blobs are shared with manifest_e
        self.assertEqual(latest.content_summary.added["container.blob"]["count"], 5)

        # Actual test
        remove_response = self.repositories_api.remove(
            self.to_repo.pulp_href, {"content_units": [manifest_e]}
        )
        monitor_task(remove_response.task)
        latest_version_href = self.repositories_api.read(self.to_repo.pulp_href).latest_version_href
        latest = self.versions_api.read(latest_version_href)
        self.assertFalse("container.tag" in latest.content_summary.removed)
        self.assertEqual(latest.content_summary.removed["container.manifest"]["count"], 1)
        # Despite having 4 blobs, only 2 are removed, 2 is shared with manifest_a.
        self.assertEqual(latest.content_summary.removed["container.blob"]["count"], 2)

    def test_manifest_lists_shared_manifests(self):
        """Starting with 2 manifest lists that share a manifest, remove one of them."""
        ml_i = (
            self.tags_api.list(name="ml_i", repository_version=self.latest_from_version)
            .results[0]
            .tagged_manifest
        )
        # Shares 1 manifest with ml_i
        ml_iii = (
            self.tags_api.list(name="ml_iii", repository_version=self.latest_from_version)
            .results[0]
            .tagged_manifest
        )
        add_response = self.repositories_api.add(
            self.to_repo.pulp_href, {"content_units": [ml_i, ml_iii]}
        )
        monitor_task(add_response.task)
        latest_version_href = self.repositories_api.read(self.to_repo.pulp_href).latest_version_href
        latest = self.versions_api.read(latest_version_href)
        # Ensure valid starting state
        self.assertFalse("container.tag" in latest.content_summary.added)
        # 2 manifest lists, each with 2 manifests, 1 manifest shared
        self.assertEqual(latest.content_summary.added["container.manifest"]["count"], 5)
        self.assertEqual(latest.content_summary.added["container.blob"]["count"], 7)

        # Actual test
        remove_response = self.repositories_api.remove(
            self.to_repo.pulp_href, {"content_units": [ml_iii]}
        )
        monitor_task(remove_response.task)
        latest_version_href = self.repositories_api.read(self.to_repo.pulp_href).latest_version_href
        latest = self.versions_api.read(latest_version_href)
        self.assertFalse("container.tag" in latest.content_summary.removed)
        # 1 manifest list, 1 manifest
        self.assertEqual(latest.content_summary.removed["container.manifest"]["count"], 2)
        self.assertEqual(latest.content_summary.removed["container.blob"]["count"], 2)

    def test_many_tagged_manifest_lists(self):
        """Add several Manifest List, related manifests, and related blobs."""
        ml_i_tag = (
            self.tags_api.list(name="ml_i", repository_version=self.latest_from_version)
            .results[0]
            .pulp_href
        )
        ml_ii_tag = (
            self.tags_api.list(name="ml_ii", repository_version=self.latest_from_version)
            .results[0]
            .pulp_href
        )
        ml_iii_tag = (
            self.tags_api.list(name="ml_iii", repository_version=self.latest_from_version)
            .results[0]
            .pulp_href
        )
        ml_iv_tag = (
            self.tags_api.list(name="ml_iv", repository_version=self.latest_from_version)
            .results[0]
            .pulp_href
        )
        add_response = self.repositories_api.add(
            self.to_repo.pulp_href, {"content_units": [ml_i_tag, ml_ii_tag, ml_iii_tag, ml_iv_tag]}
        )
        monitor_task(add_response.task)
        latest_version_href = self.repositories_api.read(self.to_repo.pulp_href).latest_version_href
        latest = self.versions_api.read(latest_version_href)

        self.assertEqual(latest.content_summary.added["container.tag"]["count"], 4)
        self.assertEqual(latest.content_summary.added["container.manifest"]["count"], 9)
        self.assertEqual(latest.content_summary.added["container.blob"]["count"], 11)

        remove_response = self.repositories_api.remove(
            self.to_repo.pulp_href, {"content_units": [ml_i_tag, ml_ii_tag, ml_iii_tag, ml_iv_tag]}
        )
        monitor_task(remove_response.task)
        latest_version_href = self.repositories_api.read(self.to_repo.pulp_href).latest_version_href
        latest = self.versions_api.read(latest_version_href)

        self.assertEqual(latest.content_summary.removed["container.tag"]["count"], 4)
        self.assertEqual(latest.content_summary.removed["container.manifest"]["count"], 9)
        self.assertEqual(latest.content_summary.removed["container.blob"]["count"], 11)

    def test_cannot_remove_tagged_manifest(self):
        """
        Try to remove a manifest (without removing tag). Creates a new version, but nothing removed.
        """
        manifest_a_tag = self.tags_api.list(
            name="manifest_a", repository_version=self.latest_from_version
        ).results[0]
        add_response = self.repositories_api.add(
            self.to_repo.pulp_href, {"content_units": [manifest_a_tag.pulp_href]}
        )
        monitor_task(add_response.task)
        latest_version_href = self.repositories_api.read(self.to_repo.pulp_href).latest_version_href
        latest = self.versions_api.read(latest_version_href)
        self.assertEqual(latest.content_summary.added["container.tag"]["count"], 1)
        self.assertEqual(latest.content_summary.added["container.manifest"]["count"], 1)
        self.assertEqual(latest.content_summary.added["container.blob"]["count"], 3)

        remove_respone = self.repositories_api.remove(
            self.to_repo.pulp_href, {"content_units": [manifest_a_tag.tagged_manifest]}
        )
        monitor_task(remove_respone.task)

        latest_version_href = self.repositories_api.read(self.to_repo.pulp_href).latest_version_href
        latest = self.versions_api.read(latest_version_href)
        for content_type in ["container.tag", "container.manifest", "container.blob"]:
            self.assertFalse(content_type in latest.content_summary.removed, msg=content_type)


class TestRecursiveRemovePushRepo(PulpTestCase, rbac_base.BaseRegistryTest):
    """Test the image removal within a push repository."""

    @classmethod
    def setUpClass(cls):
        """Define class-wide variables and initialize a repository needed later in the tests."""
        cfg = config.get_config()
        cls.registry = cli.RegistryClient(cfg)
        cls.registry.raise_if_unsupported(unittest.SkipTest, "Tests require podman/docker")
        cls.registry_name = urlparse(cfg.get_base_url()).netloc

        admin_user, admin_password = cfg.pulp_auth
        cls.user_admin = {"username": admin_user, "password": admin_password}

        api_client = gen_container_client()
        api_client.configuration.username = cls.user_admin["username"]
        api_client.configuration.password = cls.user_admin["password"]

        cls.repositories_api = RepositoriesContainerPushApi(api_client)
        cls.versions_api = RepositoriesContainerVersionsApi(api_client)
        cls.namespaces_api = PulpContainerNamespacesApi(api_client)
        cls.manifests_api = ContentManifestsApi(api_client)
        cls.distributions_api = DistributionsContainerApi(api_client)

        # the image tagged as 'manifest_a' consists of 3 blobs, 1 manifest, and 1 tag
        manifest_a_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
        cls._pull(manifest_a_path)

        local_url = "/".join([cls.registry_name, "foo/bar:tag"])
        cls._push(manifest_a_path, local_url, cls.user_admin)

        cls.repo = cls.repositories_api.list(name="foo/bar").results[0]
        cls.distribution = cls.distributions_api.list(name="foo/bar").results[0]
        cls.namespace = cls.namespaces_api.list(name="foo").results[0]

        # create a new tag to test if all tags pointing to the same manifest will be removed
        cls.manifest_a = cls.manifests_api.list().results[0]
        tag_data = TagImage(tag="new_tag", digest=cls.manifest_a.digest)
        tag_response = cls.repositories_api.tag(cls.repo.pulp_href, tag_data)
        monitor_task(tag_response.task)

        latest_version_href = cls.repositories_api.read(cls.repo.pulp_href).latest_version_href
        cls.content_to_remove = cls.versions_api.read(latest_version_href).content_summary.present

    @classmethod
    def tearDownClass(cls):
        """Delete the created namespace."""
        cls.namespaces_api.delete(cls.namespace.pulp_href)
        delete_orphans()

    def test_remove_image(self):
        """Remove the 'manifest_a' image along with the related blobs, manifest, and tags."""
        remove_response = self.repositories_api.remove_image(
            self.repo.pulp_href, RemoveImage(digest=self.manifest_a.digest)
        )
        monitor_task(remove_response.task)

        latest_version_href = self.repositories_api.read(self.repo.pulp_href).latest_version_href
        content_summary = self.versions_api.read(latest_version_href).content_summary

        self.assertEqual(content_summary.present, {})
        self.assertEqual(content_summary.added, {})

        self.assertEqual(
            content_summary.removed["container.blob"]["count"],
            self.content_to_remove["container.blob"]["count"],
        )
        self.assertEqual(
            content_summary.removed["container.manifest"]["count"],
            self.content_to_remove["container.manifest"]["count"],
        )
        self.assertEqual(
            content_summary.removed["container.tag"]["count"],
            self.content_to_remove["container.tag"]["count"],
        )

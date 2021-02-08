# coding=utf-8
"""Tests that verify that RBAC for repository versions work properly."""
import unittest

from urllib.parse import urlparse

from pulp_smash import cli, config
from pulp_smash.pulp3.bindings import monitor_task
from pulp_smash.pulp3.utils import delete_orphans, gen_repo

from pulpcore.client.pulp_container.exceptions import ApiException

from pulp_container.tests.functional.api import rbac_base
from pulp_container.tests.functional.constants import DOCKERHUB_PULP_FIXTURE_1
from pulp_container.tests.functional.utils import (
    del_user,
    gen_container_client,
    gen_container_remote,
    gen_user,
)

from pulpcore.client.pulp_container import (
    ContainerContainerRepository,
    ContentTagsApi,
    ContentManifestsApi,
    PulpContainerNamespacesApi,
    RepositoriesContainerApi,
    RepositoriesContainerPushApi,
    RepositoriesContainerVersionsApi,
    RepositorySyncURL,
)

from .test_tagging_images import TaggingTestCommons


class RepoVersionTestCase(unittest.TestCase, TaggingTestCommons):
    """Verify RBAC for repo versions of a ContainerRepository."""

    @classmethod
    def setUpClass(cls):
        """
        Define APIs to use and pull images needed later in tests
        """
        api_client = gen_container_client()
        cfg = config.get_config()

        cls.repositories_api = RepositoriesContainerApi(api_client)
        cls.repo_version_api = RepositoriesContainerVersionsApi(api_client)
        cls.tags_api = ContentTagsApi(api_client)
        cls.manifests_api = ContentManifestsApi(api_client)

        admin_user, admin_password = cfg.pulp_auth
        cls.user_admin = {"username": admin_user, "password": admin_password}
        cls.user_creator = gen_user(
            [
                "container.add_containerrepository",
                "container.add_containerremote",
            ]
        )
        cls.user_repov_remover = gen_user(
            [
                "container.delete_containerrepository_versions",
                "container.view_containerrepository",
            ]
        )
        cls.user_repo_remover = gen_user(
            [
                "container.delete_containerrepository",
                "container.view_containerrepository",
            ]
        )
        cls.user_reader = gen_user(["container.view_containerrepository"])
        cls.user_helpless = gen_user([])

        # sync a repo
        cls.repository = cls.user_creator["repository_api"].create(
            ContainerContainerRepository(**gen_repo())
        )
        cls.remote = cls.user_creator["remote_api"].create(
            gen_container_remote(upstream_name=DOCKERHUB_PULP_FIXTURE_1)
        )
        sync_data = RepositorySyncURL(remote=cls.remote.pulp_href)
        sync_response = cls.user_creator["repository_api"].sync(cls.repository.pulp_href, sync_data)
        monitor_task(sync_response.task)

    @classmethod
    def tearDownClass(cls):
        """Delete api users and things created in setUpclass."""
        cls.user_creator["repository_api"].delete(cls.repository.pulp_href)
        cls.user_creator["remote_api"].delete(cls.remote.pulp_href)
        delete_orphans()
        del_user(cls.user_creator)
        del_user(cls.user_repov_remover)
        del_user(cls.user_repo_remover)
        del_user(cls.user_reader)
        del_user(cls.user_helpless)

    def test_repov_list(self):
        """
        Test that users can list repository versions if they have enough rights
        """
        self.assertEqual(self.repo_version_api.list(self.repository.pulp_href).count, 2)
        self.assertEqual(
            self.user_creator["repo_version_api"].list(self.repository.pulp_href).count, 2
        )
        self.assertEqual(
            self.user_reader["repo_version_api"].list(self.repository.pulp_href).count, 2
        )
        with self.assertRaises(ApiException):
            self.user_helpless["repo_version_api"].list(self.repository.pulp_href)

    def test_repov_read(self):
        """
        Test that users can read specific repository versions if they have enough rights
        """
        repository = self.repositories_api.read(self.repository.pulp_href)
        self.repo_version_api.read(repository.latest_version_href)
        self.user_creator["repo_version_api"].read(repository.latest_version_href)
        self.user_reader["repo_version_api"].read(repository.latest_version_href)
        with self.assertRaises(ApiException):
            self.user_helpless["repo_version_api"].read(repository.latest_version_href)

    def test_repov_delete(self):
        """
        Test that users can delete repository versions if they have enough rights
        """

        def create_new_repo_version():
            """
            Create a new repo version to delete it later by a test user
            """
            manifest_a = self.get_manifest_by_tag("manifest_a")
            self.tag_image(manifest_a, "new_tag")
            repository = self.repositories_api.read(self.repository.pulp_href)
            return repository.latest_version_href

        repository = self.repositories_api.read(self.repository.pulp_href)
        with self.assertRaises(ApiException):
            self.user_helpless["repo_version_api"].delete(repository.latest_version_href)
        with self.assertRaises(ApiException):
            self.user_reader["repo_version_api"].delete(repository.latest_version_href)

        response = self.repo_version_api.delete(create_new_repo_version())
        monitor_task(response.task)

        response = self.user_creator["repo_version_api"].delete(create_new_repo_version())
        monitor_task(response.task)

        response = self.user_repov_remover["repo_version_api"].delete(create_new_repo_version())
        monitor_task(response.task)

        response = self.user_repo_remover["repo_version_api"].delete(create_new_repo_version())
        monitor_task(response.task)


class PushRepoVersionTestCase(unittest.TestCase, rbac_base.BaseRegistryTest):
    """Verify RBAC for repo versions of a ContainerPushRepository."""

    @classmethod
    def setUpClass(cls):
        """
        Define APIs to use and pull images needed later in tests
        """
        api_client = gen_container_client()
        cls.pushrepository_api = RepositoriesContainerPushApi(api_client)
        cls.namespace_api = PulpContainerNamespacesApi(api_client)
        cls.repo_version_api = RepositoriesContainerVersionsApi(api_client)

        cfg = config.get_config()
        cls.registry = cli.RegistryClient(cfg)
        cls.registry.raise_if_unsupported(unittest.SkipTest, "Tests require podman/docker")
        cls.registry_name = urlparse(cfg.get_base_url()).netloc

        admin_user, admin_password = cfg.pulp_auth
        cls.user_admin = {"username": admin_user, "password": admin_password}
        cls.user_creator = gen_user(
            [
                "container.add_containerdistribution",
                "container.add_containernamespace",
            ]
        )
        cls.user_reader = gen_user(["container.view_containerpushrepository"])
        cls.user_helpless = gen_user([])

        # create a push repo
        image_path = f"{DOCKERHUB_PULP_FIXTURE_1}:manifest_d"
        cls._pull(image_path)
        repo_name = "testrv/perms"
        local_url = "/".join([cls.registry_name, f"{repo_name}:1.0"])
        cls._push(image_path, local_url, cls.user_creator)
        cls.repository = cls.pushrepository_api.list(name=repo_name).results[0]

    @classmethod
    def tearDownClass(cls):
        """Delete api users and things created in setUpclass."""
        namespace = cls.namespace_api.list(name="testrv").results[0]
        cls.namespace_api.delete(namespace.pulp_href)
        delete_orphans()
        del_user(cls.user_creator)
        del_user(cls.user_reader)
        del_user(cls.user_helpless)

    def test_repov_list(self):
        """
        Test that users can list repository versions if they have enough rights
        """
        self.assertEqual(self.repo_version_api.list(self.repository.pulp_href).count, 5)
        self.assertEqual(
            self.user_creator["repo_version_api"].list(self.repository.pulp_href).count, 5
        )
        self.assertEqual(
            self.user_reader["repo_version_api"].list(self.repository.pulp_href).count, 5
        )
        with self.assertRaises(ApiException):
            self.user_helpless["repo_version_api"].list(self.repository.pulp_href)

    def test_repov_read(self):
        """
        Test that users can read specific repository versions if they have enough rights
        """
        repository = self.pushrepository_api.read(self.repository.pulp_href)
        self.repo_version_api.read(repository.latest_version_href)
        self.user_creator["repo_version_api"].read(repository.latest_version_href)
        self.user_reader["repo_version_api"].read(repository.latest_version_href)
        with self.assertRaises(ApiException):
            self.user_helpless["repo_version_api"].read(repository.latest_version_href)

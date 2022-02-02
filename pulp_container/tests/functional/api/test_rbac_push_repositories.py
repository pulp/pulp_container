# coding=utf-8
"""Tests that verify that RBAC for push repository works properly."""
import unittest

from urllib.parse import urlparse

from pulp_smash import cli, config
from pulp_smash.pulp3.bindings import delete_orphans, monitor_task

from pulpcore.client.pulp_container.exceptions import ApiException

from pulp_container.tests.functional.api import rbac_base
from pulp_container.tests.functional.constants import REGISTRY_V2_REPO_PULP
from pulp_container.tests.functional.utils import (
    del_user,
    gen_container_client,
    gen_user,
)

from pulpcore.client.pulp_container import (
    PulpContainerNamespacesApi,
    RepositoriesContainerPushApi,
)


class PushRepositoryTestCase(unittest.TestCase, rbac_base.BaseRegistryTest):
    """Verify RBAC for a ContainerPushRepository."""

    @classmethod
    def setUpClass(cls):
        """
        Define APIs to use.
        """
        api_client = gen_container_client()
        cls.pushrepository_api = RepositoriesContainerPushApi(api_client)
        cls.namespace_api = PulpContainerNamespacesApi(api_client)

        cfg = config.get_config()
        cls.registry = cli.RegistryClient(cfg)
        cls.registry.raise_if_unsupported(unittest.SkipTest, "Tests require podman/docker")
        cls.registry_name = urlparse(cfg.get_base_url()).netloc

        cls.user_creator = gen_user(
            [
                "container.add_containerdistribution",
                "container.add_containernamespace",
            ]
        )
        cls.user_reader = gen_user(["container.view_containerpushrepository"])
        cls.user_helpless = gen_user([])

        # create a push repo
        image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_d"
        cls._pull(image_path)
        repo_name = "test_push_repo/perms"
        local_url = "/".join([cls.registry_name, f"{repo_name}:1.0"])
        cls._push(image_path, local_url, cls.user_creator)
        cls.repository = cls.pushrepository_api.list(name=repo_name).results[0]

    @classmethod
    def tearDownClass(cls):
        """Delete api users and things created in setUpclass."""
        namespace = cls.namespace_api.list(name="test_push_repo").results[0]
        cls.namespace_api.delete(namespace.pulp_href)
        delete_orphans()
        del_user(cls.user_creator)
        del_user(cls.user_reader)
        del_user(cls.user_helpless)

    def test_02_read_repository(self):
        """Read a repository by its href."""
        self.user_creator["pushrepository_api"].read(self.repository.pulp_href)
        # read with global read permission
        self.user_reader["pushrepository_api"].read(self.repository.pulp_href)
        # read without read permission
        with self.assertRaises(ApiException):
            self.user_helpless["pushrepository_api"].read(self.repository.pulp_href)

    def test_02_read_repositories(self):
        """Read a repository by its name."""
        page = self.user_creator["pushrepository_api"].list(name=self.repository.name)
        self.assertEqual(len(page.results), 1)
        page = self.user_reader["pushrepository_api"].list(name=self.repository.name)
        self.assertEqual(len(page.results), 1)
        # this is a public repo
        page = self.user_helpless["pushrepository_api"].list(name=self.repository.name)
        self.assertEqual(len(page.results), 1)

    def test_03_partially_update(self):
        """Update a repository using HTTP PATCH."""
        body = {"description": "new_hotness"}
        with self.assertRaises(ApiException):
            self.user_helpless["pushrepository_api"].partial_update(self.repository.pulp_href, body)
        with self.assertRaises(ApiException):
            self.user_reader["pushrepository_api"].partial_update(self.repository.pulp_href, body)
        response = self.user_creator["pushrepository_api"].partial_update(
            self.repository.pulp_href, body
        )
        monitor_task(response.task)
        repository = self.user_creator["pushrepository_api"].read(self.repository.pulp_href)
        self.assertEqual(repository.description, body["description"])

    def test_04_fully_update(self):
        """Update a repository using HTTP PUT."""
        body = {"name": self.repository.name, "description": "old_busted"}
        with self.assertRaises(ApiException):
            self.user_helpless["pushrepository_api"].update(self.repository.pulp_href, body)
        with self.assertRaises(ApiException):
            self.user_reader["pushrepository_api"].update(self.repository.pulp_href, body)
        response = self.user_creator["pushrepository_api"].update(self.repository.pulp_href, body)
        monitor_task(response.task)
        repository = self.user_creator["pushrepository_api"].read(self.repository.pulp_href)
        self.assertEqual(repository.description, body["description"])

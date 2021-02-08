# coding=utf-8
"""Tests that verify that RBAC for content works properly."""
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
    PulpContainerNamespacesApi,
    RepositoriesContainerApi,
    RepositoriesContainerPushApi,
    RepositorySyncURL,
)


class ContainerContentTestCase(unittest.TestCase, rbac_base.BaseRegistryTest):
    """Verify RBAC for content  of a ContainerRepository."""

    @classmethod
    def setUpClass(cls):
        """
        Define APIs to use and pull images needed later in tests
        """
        api_client = gen_container_client()
        cfg = config.get_config()

        cls.repository_api = RepositoriesContainerApi(api_client)
        cls.pushrepository_api = RepositoriesContainerPushApi(api_client)
        cls.tags_api = ContentTagsApi(api_client)

        cls.namespace_api = PulpContainerNamespacesApi(api_client)
        cls.registry = cli.RegistryClient(cfg)
        cls.registry.raise_if_unsupported(unittest.SkipTest, "Tests require podman/docker")
        cls.registry_name = urlparse(cfg.get_base_url()).netloc

        admin_user, admin_password = cfg.pulp_auth
        cls.user_admin = {"username": admin_user, "password": admin_password}
        cls.user_creator = gen_user(
            [
                "container.add_containerrepository",
                "container.add_containerremote",
                "container.add_containernamespace",
                "container.add_containerdistribution",
            ]
        )
        cls.user_creator2 = gen_user(
            [
                "container.add_containernamespace",
                "container.add_containerdistribution",
            ]
        )
        cls.user_reader = gen_user(
            [
                "container.view_containerrepository",
                "container.view_containerpushrepository",
            ]
        )
        cls.user_reader2 = gen_user(["container.view_containerrepository"])
        cls.user_reader3 = gen_user(["container.view_containerpushrepository"])
        cls.user_helpless = gen_user([])

        # create a push repo with user_creator
        image_path = f"{DOCKERHUB_PULP_FIXTURE_1}:manifest_a"
        cls._pull(image_path)
        repo_name = "testcontent/perms"
        local_url = "/".join([cls.registry_name, f"{repo_name}:1.0"])
        cls._push(image_path, local_url, cls.user_creator)
        cls.push_repository = cls.pushrepository_api.list(name=repo_name).results[0]

        # create a second push repo with user_creator2
        image_path = f"{DOCKERHUB_PULP_FIXTURE_1}:manifest_b"
        cls._pull(image_path)
        repo_name = "testcontent2/perms"
        local_url = "/".join([cls.registry_name, f"{repo_name}:1.0"])
        cls._push(image_path, local_url, cls.user_creator2)
        cls.push_repository2 = cls.pushrepository_api.list(name=repo_name).results[0]

        # sync a repo with user_creator
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
        """Delete api users and objects created in setUpclass."""
        cls.user_creator["repository_api"].delete(cls.repository.pulp_href)
        cls.user_creator["remote_api"].delete(cls.remote.pulp_href)
        del_user(cls.user_creator)
        del_user(cls.user_creator2)
        del_user(cls.user_reader)
        del_user(cls.user_reader2)
        del_user(cls.user_reader3)
        del_user(cls.user_helpless)
        for name in ("testcontent", "testcontent2"):
            namespace = cls.namespace_api.list(name=name).results[0]
            cls.namespace_api.delete(namespace.pulp_href)
        delete_orphans()

    def test_content_list(self):
        """
        Test that users can list content if they have enough rights
        """
        push_repository_rv = self.pushrepository_api.read(
            self.push_repository.pulp_href
        ).latest_version_href
        push_repository2_rv = self.pushrepository_api.read(
            self.push_repository2.pulp_href
        ).latest_version_href
        repository_rv = self.repository_api.read(self.repository.pulp_href).latest_version_href

        self.assertEqual(self.user_creator["tags_api"].list().count, 10)
        self.assertEqual(
            self.user_creator["tags_api"].list(repository_version=push_repository_rv).count, 1
        )
        self.assertEqual(
            self.user_creator["tags_api"].list(repository_version=repository_rv).count, 9
        )
        self.assertEqual(
            self.user_creator["tags_api"].list(repository_version=push_repository2_rv).count, 0
        )

        self.assertEqual(self.user_creator2["tags_api"].list().count, 1)
        self.assertEqual(
            self.user_creator2["tags_api"].list(repository_version=push_repository2_rv).count, 1
        )
        self.assertEqual(
            self.user_creator2["tags_api"].list(repository_version=push_repository_rv).count, 0
        )
        self.assertEqual(
            self.user_creator2["tags_api"].list(repository_version=repository_rv).count, 0
        )

        self.assertEqual(self.user_reader["tags_api"].list().count, 11)
        self.assertEqual(
            self.user_reader["tags_api"].list(repository_version=push_repository2_rv).count, 1
        )
        self.assertEqual(
            self.user_reader["tags_api"].list(repository_version=push_repository_rv).count, 1
        )
        self.assertEqual(
            self.user_reader["tags_api"].list(repository_version=repository_rv).count, 9
        )

        self.assertEqual(self.user_reader2["tags_api"].list().count, 9)
        self.assertEqual(
            self.user_reader2["tags_api"].list(repository_version=push_repository2_rv).count, 0
        )
        self.assertEqual(
            self.user_reader2["tags_api"].list(repository_version=push_repository_rv).count, 0
        )
        self.assertEqual(
            self.user_reader2["tags_api"].list(repository_version=repository_rv).count, 9
        )

        self.assertEqual(self.user_reader3["tags_api"].list().count, 2)
        self.assertEqual(
            self.user_reader3["tags_api"].list(repository_version=push_repository2_rv).count, 1
        )
        self.assertEqual(
            self.user_reader3["tags_api"].list(repository_version=push_repository_rv).count, 1
        )
        self.assertEqual(
            self.user_reader3["tags_api"].list(repository_version=repository_rv).count, 0
        )

        self.assertEqual(self.user_helpless["tags_api"].list().count, 0)
        self.assertEqual(
            self.user_helpless["tags_api"].list(repository_version=push_repository2_rv).count, 0
        )
        self.assertEqual(
            self.user_helpless["tags_api"].list(repository_version=push_repository_rv).count, 0
        )
        self.assertEqual(
            self.user_helpless["tags_api"].list(repository_version=repository_rv).count, 0
        )

    def test_content_read(self):
        """
        Test that users can read specific content if they have enough rights.
        """
        push_repository = self.pushrepository_api.read(self.push_repository.pulp_href)

        pushed_tag_user_creator = self.tags_api.list(
            repository_version_added=push_repository.latest_version_href
        ).results[0]
        self.tags_api.read(pushed_tag_user_creator.pulp_href)
        self.user_creator["tags_api"].read(pushed_tag_user_creator.pulp_href)
        self.user_reader["tags_api"].read(pushed_tag_user_creator.pulp_href)
        self.user_reader3["tags_api"].read(pushed_tag_user_creator.pulp_href)
        with self.assertRaises(ApiException):
            self.user_creator2["tags_api"].read(pushed_tag_user_creator.pulp_href)
        with self.assertRaises(ApiException):
            self.user_reader2["tags_api"].read(pushed_tag_user_creator.pulp_href)
        with self.assertRaises(ApiException):
            self.user_helpless["tags_api"].read(pushed_tag_user_creator.pulp_href)

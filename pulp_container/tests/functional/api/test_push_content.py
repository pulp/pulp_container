# coding=utf-8
"""Tests that verify that images can be pushed to Pulp."""
import unittest

from urllib.parse import urlparse

from pulp_smash import cli, config, exceptions
from pulp_smash.pulp3.bindings import (
    delete_orphans,
    monitor_task,
    PulpTestCase,
)
from pulp_container.tests.functional.api import rbac_base
from pulp_container.tests.functional.constants import REGISTRY_V2_REPO_PULP
from pulp_container.tests.functional.utils import (
    add_user_to_distribution_group,
    add_user_to_namespace_group,
    del_user,
    gen_container_client,
    gen_user,
)

from pulpcore.client.pulp_container import (
    PulpContainerNamespacesApi,
    RepositoriesContainerPushApi,
)


class PushRepoTestCase(PulpTestCase, rbac_base.BaseRegistryTest):
    """Verify whether images can be pushed to pulp."""

    @classmethod
    def setUpClass(cls):
        """
        Define APIs to use and pull images needed later in tests
        """
        cfg = config.get_config()
        cls.registry = cli.RegistryClient(cfg)
        cls.registry.raise_if_unsupported(unittest.SkipTest, "Tests require podman/docker")
        cls.registry_name = urlparse(cfg.get_base_url()).netloc

        admin_user, admin_password = cfg.pulp_auth
        cls.user_admin = {"username": admin_user, "password": admin_password}
        cls.user_creator = gen_user(
            ["container.add_containernamespace", "container.add_containerdistribution"]
        )
        cls.user_dist_collaborator = gen_user([])
        cls.user_dist_consumer = gen_user([])
        cls.user_namespace_collaborator = gen_user([])
        cls.user_reader = gen_user([])
        cls.user_helpless = gen_user([])

        # View push repositories, distributions, and namespaces using user_creator.
        api_client = gen_container_client()
        api_client.configuration.username = cls.user_admin["username"]
        api_client.configuration.password = cls.user_admin["password"]
        cls.pushrepository_api = RepositoriesContainerPushApi(api_client)
        cls.namespace_api = PulpContainerNamespacesApi(api_client)

        cls._pull(f"{REGISTRY_V2_REPO_PULP}:manifest_a")
        cls._pull(f"{REGISTRY_V2_REPO_PULP}:manifest_b")
        cls._pull(f"{REGISTRY_V2_REPO_PULP}:manifest_c")
        cls._pull(f"{REGISTRY_V2_REPO_PULP}:manifest_d")

    @classmethod
    def tearDownClass(cls):
        """Delete api users."""
        del_user(cls.user_creator)
        del_user(cls.user_dist_collaborator)
        del_user(cls.user_dist_consumer)
        del_user(cls.user_namespace_collaborator)
        del_user(cls.user_reader)
        del_user(cls.user_helpless)
        delete_orphans()

    def test_push_using_registry_client_admin(self):
        """Test push with official registry client and logged in as admin."""
        image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
        local_url = "/".join([self.registry_name, "foo/bar:1.0"])

        self._push(image_path, local_url, self.user_admin)
        self._pull(local_url, self.user_admin)

        # cleanup, namespace removal also removes related distributions
        namespace = self.namespace_api.list(name="foo").results[0]
        self.addCleanup(self.namespace_api.delete, namespace.pulp_href)

    def test_push_without_login(self):
        """Test that one can't push without being logged in."""
        local_url = "/".join([self.registry_name, "foo/bar:1.0"])

        # Try to push without permission
        with self.assertRaises(exceptions.CalledProcessError):
            self.registry.push(local_url)

    def test_push_with_dist_perms(self):
        """
        Test that it's enough to have container distribution and namespace perms to perform push.

        It also checks read abilities for users with different set of permissions.
        """
        repo_name = "test/perms"
        local_url = "/".join([self.registry_name, f"{repo_name}:2.0"])
        image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
        self._push(image_path, local_url, self.user_creator)

        distributions = self.user_creator["distribution_api"].list(name="test/perms")
        add_user_to_distribution_group(
            self.user_dist_collaborator,
            distributions.results[0],
            "collaborators",
            self.user_creator,
        )

        distributions = self.user_creator["distribution_api"].list(name="test/perms")
        add_user_to_distribution_group(
            self.user_dist_consumer,
            distributions.results[0],
            "consumers",
            self.user_creator,
        )

        add_user_to_namespace_group(
            self.user_namespace_collaborator,
            "test",
            "collaborators",
            self.user_creator,
        )

        self.assertEqual(self.pushrepository_api.list(name=repo_name).count, 1)
        self.assertEqual(self.user_creator["pushrepository_api"].list(name=repo_name).count, 1)
        self.assertEqual(
            self.user_dist_collaborator["pushrepository_api"].list(name=repo_name).count, 1
        )
        self.assertEqual(
            self.user_dist_consumer["pushrepository_api"].list(name=repo_name).count, 1
        )
        self.assertEqual(
            self.user_namespace_collaborator["pushrepository_api"].list(name=repo_name).count, 1
        )

        self.assertEqual(self.user_reader["pushrepository_api"].list(name=repo_name).count, 1)

        # cleanup, namespace removal also removes related distributions
        namespace = self.namespace_api.list(name="test").results[0]
        self.addCleanup(self.namespace_api.delete, namespace.pulp_href)

    def test_push_with_view_perms(self):
        """
        Test that push is not working if a user has only view permission for push repos.
        """
        repo_name = "unsuccessful/perms"
        local_url = "/".join([self.registry_name, f"{repo_name}:2.0"])
        image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
        with self.assertRaises(exceptions.CalledProcessError):
            self._push(image_path, local_url, self.user_reader)

    def test_push_with_no_perms(self):
        """
        Test that user with no permissions can't perform push.
        """
        repo_name = "unsuccessful/perms"
        local_url = "/".join([self.registry_name, f"{repo_name}:2.0"])
        image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
        with self.assertRaises(exceptions.CalledProcessError):
            self._push(image_path, local_url, self.user_helpless)

        # test a user can still pull
        self._push(image_path, local_url, self.user_creator)
        with self.assertRaises(exceptions.CalledProcessError):
            self._push(image_path, local_url, self.user_dist_consumer)
        self._pull(local_url, self.user_dist_consumer)

        # cleanup, namespace removal also removes related distributions
        namespace = self.namespace_api.list(name="unsuccessful").results[0]
        self.addCleanup(self.namespace_api.delete, namespace.pulp_href)

    def test_push_to_existing_namespace(self):
        """
        Test the push to existing namespace with collaborator permissions.

        Container distribution perms and manage-namespace one should be enough
        to push a new distribution.
        Container distribution perms shouls be enough to push to the existing
        distribution.
        """
        repo_name = "team/owner"
        local_url = "/".join([self.registry_name, f"{repo_name}:2.0"])
        image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
        self._push(image_path, local_url, self.user_creator)

        # Add user_dist_collaborator to the collaborator group
        distributions = self.user_creator["distribution_api"].list(name="team/owner")
        add_user_to_distribution_group(
            self.user_dist_collaborator,
            distributions.results[0],
            "collaborators",
            self.user_creator,
        )

        collab_repo_name = "team/owner"
        local_url = "/".join([self.registry_name, f"{collab_repo_name}:2.0"])
        image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_b"
        self._push(image_path, local_url, self.user_dist_collaborator)

        collab_repo_name = "team/collab"
        local_url = "/".join([self.registry_name, f"{collab_repo_name}:2.0"])
        image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_d"
        with self.assertRaises(exceptions.CalledProcessError):
            self._push(image_path, local_url, self.user_dist_collaborator)

        add_user_to_namespace_group(
            self.user_namespace_collaborator, "team", "collaborators", self.user_creator
        )

        collab_repo_name = "team/collab"
        local_url = "/".join([self.registry_name, f"{collab_repo_name}:2.0"])
        image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_c"
        self._push(image_path, local_url, self.user_namespace_collaborator)

        # cleanup, namespace removal also removes related distributions
        namespace = self.namespace_api.list(name="team").results[0]
        self.addCleanup(self.namespace_api.delete, namespace.pulp_href)

    def test_private_repository(self):
        """
        Test that you can create a private distribution and push to it.
        Test that the same user can pull, but another cannot.
        Test that the other user can pull after marking it non-private.
        """
        # cleanup, namespace removal also removes related distributions
        try:
            namespace = self.namespace_api.list(name="test").results[0]
            namespace_response = self.namespace_api.delete(namespace.pulp_href)
            monitor_task(namespace_response.task)
        except Exception:
            pass

        repo_name = "test/private"
        local_url = "/".join([self.registry_name, f"{repo_name}:2.0"])
        image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"

        distribution = {"name": "test/private", "base_path": "test/private", "private": True}
        distribution_response = self.user_creator["distribution_api"].create(distribution)
        created_resources = monitor_task(distribution_response.task).created_resources
        distribution = self.user_creator["distribution_api"].read(created_resources[0])

        self._push(image_path, local_url, self.user_creator)

        self._pull(local_url, self.user_creator)

        add_user_to_distribution_group(
            self.user_dist_consumer, distribution, "consumers", self.user_creator
        )

        self._pull(local_url, self.user_dist_consumer)
        with self.assertRaises(exceptions.CalledProcessError):
            self._pull(local_url, self.user_reader)
        with self.assertRaises(exceptions.CalledProcessError):
            self._pull(local_url, self.user_helpless)

        distribution.private = False
        distribution_response = self.user_creator["distribution_api"].partial_update(
            distribution.pulp_href, {"private": False}
        )
        monitor_task(distribution_response.task)

        self._pull(local_url, self.user_reader)
        self._pull(local_url, self.user_helpless)

        # cleanup, namespace removal also removes related distributions
        namespace = self.namespace_api.list(name="test").results[0]
        self.addCleanup(self.namespace_api.delete, namespace.pulp_href)

    def test_matching_username(self):
        """
        Test that you can push to a nonexisting nameespace that matches your username.
        """
        namespace_name = self.user_helpless["username"]
        repo_name = f"{namespace_name}/matching"
        local_url = "/".join([self.registry_name, f"{repo_name}:2.0"])
        invalid_local_url = "/".join([self.registry_name, f"other/{repo_name}:2.0"])
        image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"

        self._push(image_path, local_url, self.user_helpless)

        with self.assertRaises(exceptions.CalledProcessError):
            self._push(image_path, invalid_local_url, self.user_helpless)

        # test you can create distribution under the namespace that matches login
        repo_name2 = f"{namespace_name}/matching2"
        distribution = {"name": repo_name2, "base_path": repo_name2, "private": True}
        distribution_response = self.user_helpless["distribution_api"].create(distribution)
        created_resources = monitor_task(distribution_response.task).created_resources
        distribution = self.user_helpless["distribution_api"].read(created_resources[0])

        # cleanup, namespace removal also removes related distributions
        namespace = self.namespace_api.list(name=namespace_name).results[0]
        namespace_response = self.namespace_api.delete(namespace.pulp_href)
        monitor_task(namespace_response.task)

        # test you can create distribution if namespace does not exist but matches login
        distribution = {"name": repo_name, "base_path": repo_name, "private": True}
        distribution_response = self.user_helpless["distribution_api"].create(distribution)
        created_resources = monitor_task(distribution_response.task).created_resources
        distribution = self.user_helpless["distribution_api"].read(created_resources[0])

        # cleanup, namespace removal also removes related distributions
        namespace = self.namespace_api.list(name=namespace_name).results[0]
        self.addCleanup(self.namespace_api.delete, namespace.pulp_href)

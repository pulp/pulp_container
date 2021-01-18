# coding=utf-8
"""Tests that verify that images can be pushed to Pulp."""
import unittest

from urllib.parse import urlparse

from pulp_smash import cli, config, exceptions

from pulp_container.tests.functional.constants import DOCKERHUB_PULP_FIXTURE_1
from pulp_container.tests.functional.utils import del_user, gen_container_client, gen_user

from pulpcore.client.pulp_container import (
    PulpContainerNamespacesApi,
    RepositoriesContainerPushApi,
)


class PushRepoTestCase(unittest.TestCase):
    """Verify whether images can be pushed to pulp."""

    @classmethod
    def setUpClass(cls):
        """
        Define APIs to use and pull images needed later in tests
        """
        api_client = gen_container_client()
        cls.pushrepository_api = RepositoriesContainerPushApi(api_client)
        cls.namespace_api = PulpContainerNamespacesApi(api_client)

        cfg = config.get_config()
        cls.registry = cli.RegistryClient(cfg)
        cls.registry.raise_if_unsupported(unittest.SkipTest, "Tests require podman/docker")
        cls.registry_name = urlparse(cfg.get_base_url()).netloc

        admin_user, admin_password = cfg.pulp_auth
        cls.user_admin = {"username": admin_user, "password": admin_password}
        cls.user_creator = gen_user(
            [
                "container.add_containerdistribution",
                "container.view_containerdistribution",
                "container.add_containernamespace",
            ]
        )
        cls.user_collaborator = gen_user(
            [
                "container.add_containerdistribution",
                "container.view_containerdistribution",
                "container.manage_namespace_distributions",
                "container.view_containerpushrepository",
            ]
        )
        cls.user_reader = gen_user(["container.view_containerpushrepository"])
        cls.user_helpless = gen_user([])

        cls._pull("centos:7")
        cls._pull(f"{DOCKERHUB_PULP_FIXTURE_1}:manifest_a")
        cls._pull(f"{DOCKERHUB_PULP_FIXTURE_1}:manifest_b")

    @classmethod
    def tearDownClass(cls):
        """Delete api users."""
        del_user(cls.user_creator)
        del_user(cls.user_collaborator)
        del_user(cls.user_reader)
        del_user(cls.user_helpless)

    @classmethod
    def _pull(cls, image_path, user=None):
        """
        Pull using specified user.

        Ensure we login with a user if specified and logout after the pull.

        If user is not specified, ensure that no other user is logged in and pull is performed
        anonymously.
        """
        if user:
            cls.registry.login("-u", user["username"], "-p", user["password"], cls.registry_name)
        else:
            # Ensure logout
            try:
                cls.registry.logout(cls.registry_name)
            except exceptions.CalledProcessError:
                pass

        cls.registry.pull(image_path)

        if user:
            cls.registry.logout(cls.registry_name)

    @classmethod
    def _push(cls, image_path, local_url, user):
        """
        Tag and push an image to Pulp registry using specified user.

        Ensure we login with a specified user and logout after the push.
        A local tag is removed for cleanup purposes.
        """
        # Tag it to registry under test
        cls.registry.tag(image_path, local_url)
        # Log in
        cls.registry.login("-u", user["username"], "-p", user["password"], cls.registry_name)
        try:
            cls.registry.push(local_url)
        finally:
            # Untag local copy
            cls.registry.rmi(local_url)

            cls.registry.logout(cls.registry_name)

    def test_push_using_registry_client_admin(self):
        """Test push with official registry client and logged in as admin."""
        image_path = "centos:7"
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
        image_path = f"{DOCKERHUB_PULP_FIXTURE_1}:manifest_a"
        self._push(image_path, local_url, self.user_creator)

        self.assertEqual(self.pushrepository_api.list(name=repo_name).count, 1)
        self.assertEqual(self.user_creator["pushrepository_api"].list(name=repo_name).count, 1)
        self.assertEqual(self.user_collaborator["pushrepository_api"].list(name=repo_name).count, 1)
        self.assertEqual(self.user_reader["pushrepository_api"].list(name=repo_name).count, 1)
        self.assertEqual(self.user_helpless["pushrepository_api"].list(name=repo_name).count, 0)

        # cleanup, namespace removal also removes related distributions
        namespace = self.namespace_api.list(name="test").results[0]
        self.addCleanup(self.namespace_api.delete, namespace.pulp_href)

    def test_push_with_view_perms(self):
        """
        Test that push is not working if a user has only view permission for push repos.
        """
        repo_name = "unsuccessful/perms"
        local_url = "/".join([self.registry_name, f"{repo_name}:2.0"])
        image_path = f"{DOCKERHUB_PULP_FIXTURE_1}:manifest_a"
        with self.assertRaises(exceptions.CalledProcessError):
            self._push(image_path, local_url, self.user_reader)

    def test_push_with_no_perms(self):
        """
        Test that user with no permissions can't perform push.
        """
        repo_name = "unsuccessful/perms"
        local_url = "/".join([self.registry_name, f"{repo_name}:2.0"])
        image_path = f"{DOCKERHUB_PULP_FIXTURE_1}:manifest_a"
        with self.assertRaises(exceptions.CalledProcessError):
            self._push(image_path, local_url, self.user_helpless)

    def test_push_to_existing_namespace(self):
        """
        Test the push to existing namespace with collaborator permissions.

        Container distribution perms and manage-namespace one should be enough.
        """
        repo_name = "team/owner"
        local_url = "/".join([self.registry_name, f"{repo_name}:2.0"])
        image_path = f"{DOCKERHUB_PULP_FIXTURE_1}:manifest_a"
        self._push(image_path, local_url, self.user_creator)

        collab_repo_name = "team/owner"
        local_url = "/".join([self.registry_name, f"{collab_repo_name}:2.0"])
        image_path = f"{DOCKERHUB_PULP_FIXTURE_1}:manifest_b"
        self._push(image_path, local_url, self.user_collaborator)

        # cleanup, namespace removal also removes related distributions
        namespace = self.namespace_api.list(name="team").results[0]
        self.addCleanup(self.namespace_api.delete, namespace.pulp_href)

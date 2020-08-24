# coding=utf-8
"""Tests that verify that images can be pushed to Pulp."""
import unittest

from pulp_smash import cli, config, exceptions

from pulp_container.tests.functional.utils import gen_container_client

from pulpcore.client.pulp_container import RepositoriesContainerPushApi


cfg = config.get_config()

api_client = gen_container_client()
push_repositories_api = RepositoriesContainerPushApi(api_client)

registry = cli.RegistryClient(cfg)


class PushContentTestCase(unittest.TestCase):
    """Verify whether images can be pushed to pulp."""

    def test_push_using_registry_client(self):
        """Test push with official registry client"""
        registry.raise_if_unsupported(unittest.SkipTest, "Test requires podman/docker")
        # TODO better handling of the "http://"
        registry_name = cfg.get_base_url()[7:]
        local_url = "/".join([registry_name, "foo/bar:1.0"])
        # Be sure to not being logged in
        try:
            registry.logout(registry_name)
        except exceptions.CalledProcessError:
            pass
        # Pull an image with large blobs
        registry.pull("centos:7")
        # Tag it to registry under test
        registry.tag("centos:7", local_url)
        # Try to push without permission
        with self.assertRaises(exceptions.CalledProcessError):
            registry.push(local_url)
        # Log in
        registry.login("-u", "admin", "-p", "password", registry_name)
        # Push successfully
        registry.push(local_url)
        # Pull while logged in
        registry.pull(local_url)
        # Log out
        registry.logout(registry_name)
        # Untag local copy
        registry.rmi(local_url)
        # Pull while logged out
        registry.pull(local_url)
        # cleanup
        repository = push_repositories_api.list(name="foo/bar").results[0]
        self.addCleanup(push_repositories_api.delete, repository.pulp_href)

# coding=utf-8
"""Tests that verify that images can be pushed to Pulp."""
import unittest

from pulp_smash import cli, config

from pulp_container.tests.functional.utils import (
    gen_container_client,
    gen_token_signing_keys,
)

from pulpcore.client.pulp_container import (
    DistributionsContainerApi,
    RepositoriesContainerApi,
)


cfg = config.get_config()
gen_token_signing_keys(cfg)

api_client = gen_container_client()
repositories_api = RepositoriesContainerApi(api_client)
distributions_api = DistributionsContainerApi(api_client)

registry = cli.RegistryClient(cfg)


class PushContentTestCase(unittest.TestCase):
    """Verify whether images can be pushed to pulp."""

    def test_push_using_registry_client(self):
        """Test push with official registry client"""
        registry.raise_if_unsupported(unittest.SkipTest, "Test requires podman/docker")
        # TODO better handling of the "http://"
        registry_name = cfg.get_base_url()[7:]
        local_url = "/".join([registry_name, "foo/bar:1.0"])
        registry.logout(registry_name)
        registry.pull("centos:7")
        registry.tag("centos:7", local_url)
        registry.login("-u", "admin", "-p", "password", registry_name)
        registry.push(local_url)
        registry.logout(registry_name)
        registry.pull(local_url)
        repository = repositories_api.list(name="foo/bar").results[0]
        distribution = distributions_api.list(name="foo/bar").results[0]
        self.addCleanup(repositories_api.delete, repository.pulp_href)
        self.addCleanup(distributions_api.delete, distribution.pulp_href)

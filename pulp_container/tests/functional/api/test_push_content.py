# coding=utf-8
"""Tests that verify that images can be pushed to Pulp."""
import unittest
from urllib.parse import urljoin

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

    def test_push_using_podman(self):
        """Test push with official registry client"""
        # TODO better handling of the "http://"
        local_url = urljoin(cfg.get_base_url(), 'foo/bar:1.0')[7:]
        registry.pull("busybox:latest")
        registry.tag("busybox:latest", local_url)
        registry.push(local_url)
        repository = repositories_api.list(name='foo/bar').results[0]
        distribution = distributions_api.list(name='foo/bar').results[0]
        self.addCleanup(repositories_api.delete, repository.pulp_href)
        self.addCleanup(distributions_api.delete, distribution.pulp_href)

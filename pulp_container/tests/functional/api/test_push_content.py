# coding=utf-8
"""Tests that verify that images can be pushed to Pulp."""
import unittest
from urllib.parse import urljoin

from pulp_smash import cli, config
from pulp_smash.pulp3.utils import (
    gen_distribution,
    gen_repo,
)

from pulp_container.tests.functional.utils import (
    gen_container_client,
    gen_token_signing_keys,
    monitor_task,
)

from pulpcore.client.pulp_container import (
    ContainerContainerDistribution,
    ContainerContainerRepository,
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

    def setUp(self):
        """Create class-wide variables.

        1. Create a repository.
        2. Create a container distribution to serve the repository
        """
        # Step 1
        self.repo = repositories_api.create(ContainerContainerRepository(**gen_repo()))
        # cls.teardown_cleanups.append((cls.repositories_api.delete, _repo.pulp_href))
        self.addCleanup(repositories_api.delete, self.repo.pulp_href)

        # Step 2
        distribution_response = distributions_api.create(
            ContainerContainerDistribution(
                **gen_distribution(repository=self.repo.pulp_href)
            )
        )
        created_resources = monitor_task(distribution_response.task)
        self.distribution = distributions_api.read(created_resources[0])
        self.addCleanup(distributions_api.delete, self.distribution.pulp_href)

    def test_push_using_podman(self):
        """Test push with official registry client"""
        # TODO better handling of the "http://"
        local_url = urljoin(cfg.get_base_url(), self.distribution.base_path)[7:]
        registry.pull("busybox:latest")
        registry.tag("busybox:latest", local_url)
        registry.push(local_url)
        self.assertTrue(True)

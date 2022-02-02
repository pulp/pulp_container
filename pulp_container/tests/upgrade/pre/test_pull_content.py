# coding=utf-8
"""Tests that verify that images served by Pulp can be pulled."""
import contextlib
import unittest
from urllib.parse import urljoin, urlparse

from pulp_smash import api, cli, config
from pulp_smash.pulp3.bindings import monitor_task
from pulp_smash.pulp3.utils import (
    gen_distribution,
    gen_repo,
)

from pulp_container.tests.functional.utils import (
    gen_container_client,
    gen_container_remote,
)
from pulp_container.tests.functional.constants import (
    PULP_HELLO_WORLD_LINUX_TAG,
    REGISTRY_V2_REPO_HELLO_WORLD,
)

from pulpcore.client.pulp_container import (
    ContainerContainerDistribution,
    ContainerContainerRepository,
    DistributionsContainerApi,
    RepositorySyncURL,
    RepositoriesContainerApi,
    RemotesContainerApi,
)


class PullContentTestCase(unittest.TestCase):
    """Verify whether images served by Pulp can be pulled."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables.

        1. Create a repository.
        2. Create a remote pointing to external registry.
        3. Sync the repository using the remote and re-read the repo data.
        4. Create a container distribution to serve the repository

        This tests targets the following issue:

        * `Pulp #4460 <https://pulp.plan.io/issues/4460>`_
        """
        cls.cfg = config.get_config()
        cls.registry_name = urlparse(cls.cfg.get_base_url()).netloc

        cls.client = api.Client(cls.cfg, api.code_handler)
        client_api = gen_container_client()
        cls.repositories_api = RepositoriesContainerApi(client_api)
        cls.remotes_api = RemotesContainerApi(client_api)
        cls.distributions_api = DistributionsContainerApi(client_api)

        with contextlib.ExitStack() as stack:
            # ensure tearDownClass runs if an error occurs here
            stack.callback(cls.tearDownClass)

            # Step 1
            _repo = cls.repositories_api.create(ContainerContainerRepository(**gen_repo()))

            # Step 2
            cls.remote = cls.remotes_api.create(gen_container_remote())

            # Step 3
            sync_data = RepositorySyncURL(remote=cls.remote.pulp_href)
            sync_response = cls.repositories_api.sync(_repo.pulp_href, sync_data)
            monitor_task(sync_response.task)
            cls.repo = cls.repositories_api.read(_repo.pulp_href)

            # Step 4.
            distribution_response = cls.distributions_api.create(
                ContainerContainerDistribution(
                    **gen_distribution(
                        repository=cls.repo.pulp_href, base_path="pulp_pre_upgrade_test"
                    )
                )
            )
            created_resources = monitor_task(distribution_response.task).created_resources
            distribution = cls.distributions_api.read(created_resources[0])
            cls.distribution_with_repo = cls.distributions_api.read(distribution.pulp_href)

            # remove callback if everything goes well
            stack.pop_all()

    def test_pull_image_with_tag(self):
        """Verify that a client can pull the image from Pulp with a tag.

        1. Using the RegistryClient pull the image from Pulp specifying a tag.
        2. Pull the same image and same tag from remote registry.
        3. Verify both images has the same checksum.
        4. Ensure image is deleted after the test.
        """
        registry = cli.RegistryClient(self.cfg)
        registry.raise_if_unsupported(unittest.SkipTest, "Test requires podman/docker")
        registry.login("-u", "admin", "-p", "password", self.registry_name)

        local_url = (
            urljoin(self.cfg.get_base_url(), self.distribution_with_repo.base_path)
            + PULP_HELLO_WORLD_LINUX_TAG
        )

        registry.pull(local_url)
        local_image = registry.inspect(local_url)

        registry.pull(REGISTRY_V2_REPO_HELLO_WORLD + PULP_HELLO_WORLD_LINUX_TAG)
        remote_image = registry.inspect(REGISTRY_V2_REPO_HELLO_WORLD + PULP_HELLO_WORLD_LINUX_TAG)

        self.assertEqual(local_image[0]["Id"], remote_image[0]["Id"])

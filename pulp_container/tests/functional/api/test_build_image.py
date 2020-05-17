# coding=utf-8
"""Tests that verify that images served by Pulp can be pulled."""
import contextlib
import unittest
from tempfile import NamedTemporaryFile
from urllib.parse import urljoin

from pulp_smash import cli, config
from pulp_smash.pulp3.utils import (
    gen_distribution,
    gen_repo,
)
from pulp_smash.pulp3.bindings import monitor_task

from pulp_container.tests.functional.utils import (
    core_client,
    gen_container_client,
)

from pulpcore.client.pulpcore import ArtifactsApi

from pulpcore.client.pulp_container import (
    ContainerContainerDistribution,
    ContainerContainerRepository,
    DistributionsContainerApi,
    RepositoriesContainerApi,
)


class BuildImageTestCase(unittest.TestCase):
    """Verify that an image can be built from Containerfile."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables.

        1. Create a repository.
        2. Create an artifact with some text in it.
        3. Create a Containerfile that references this artifact.
        4. Create a repository version by building an image from the Containerfile and the artifact.
        5. Create a container distribution to serve the repository version
        """
        cls.cfg = config.get_config()

        client_api = gen_container_client()
        cls.artifacts_api = ArtifactsApi(core_client)
        cls.repositories_api = RepositoriesContainerApi(client_api)
        cls.distributions_api = DistributionsContainerApi(client_api)

        cls.teardown_cleanups = []

        with contextlib.ExitStack() as stack:
            # ensure tearDownClass runs if an error occurs here
            stack.callback(cls.tearDownClass)

            # Step 1
            _repo = cls.repositories_api.create(ContainerContainerRepository(**gen_repo()))
            cls.teardown_cleanups.append((cls.repositories_api.delete, _repo.pulp_href))

            # Step 2
            with NamedTemporaryFile() as text_file:
                text_file.write(b"some text")
                text_file.flush()
                artifact = cls.artifacts_api.create(file=text_file.name)
                cls.teardown_cleanups.append((cls.artifacts_api.delete, artifact.pulp_href))

            # Step 3
            with NamedTemporaryFile() as containerfile:
                containerfile.write(
                    b"""FROM busybox:latest

# Copy a file using COPY statement. Use the relative path specified in the 'artifacts' parameter.
COPY foo/bar/example.txt /inside-image.txt

# Print the content of the file when the container starts
CMD ["cat", "/inside-image.txt"]"""
                )
                containerfile.flush()
                # Step 4
                artifacts = '{{"{}": "foo/bar/example.txt"}}'.format(artifact.pulp_href)
                build_response = cls.repositories_api.build_image(
                    _repo.pulp_href, containerfile=containerfile.name, artifacts=artifacts
                )
                monitor_task(build_response.task)
                cls.repo = cls.repositories_api.read(_repo.pulp_href)

            # Step 5.
            distribution_response = cls.distributions_api.create(
                ContainerContainerDistribution(**gen_distribution(repository=cls.repo.pulp_href))
            )
            created_resources = monitor_task(distribution_response.task)
            distribution = cls.distributions_api.read(created_resources[0])
            cls.distribution_with_repo = cls.distributions_api.read(distribution.pulp_href)
            cls.teardown_cleanups.append(
                (cls.distributions_api.delete, cls.distribution_with_repo.pulp_href)
            )

            # remove callback if everything goes well
            stack.pop_all()

    @classmethod
    def tearDownClass(cls):
        """Clean class-wide variable."""
        for cleanup_function, args in reversed(cls.teardown_cleanups):
            cleanup_function(args)

    def test_build_image_with_artifact_and_pull_from_repository(self):
        """Verify that a client can pull the image from Pulp.

        1. Using the RegistryClient pull the image from Pulp.
        2. Ensure image is deleted after the test.
        """
        registry = cli.RegistryClient(self.cfg)
        registry.raise_if_unsupported(unittest.SkipTest, "Test requires podman/docker")

        local_url = urljoin(
            self.cfg.get_content_host_base_url(), self.distribution_with_repo.base_path
        )

        registry.pull(local_url)
        self.teardown_cleanups.append((registry.rmi, local_url))
        registry.inspect(local_url)

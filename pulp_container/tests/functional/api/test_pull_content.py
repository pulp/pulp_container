"""Tests that verify that images served by Pulp can be pulled."""

import pytest
import hashlib
import requests
import subprocess

from urllib.parse import urljoin

from pulp_container.tests.functional.utils import (
    get_blobsums_from_remote_registry,
    get_auth_for_url,
)
from pulp_container.tests.functional.constants import (
    REGISTRY_V2_REPO_HELLO_WORLD,
    PULP_HELLO_WORLD_LINUX_TAG,
)
from pulp_container.constants import EMPTY_BLOB, EMPTY_JSON, MEDIA_TYPE


class TestPullContent:
    """Verify whether images served by Pulp can be pulled."""

    @pytest.fixture(scope="class")
    def setup(
        self,
        container_repository_factory,
        container_remote_factory,
        container_sync,
        container_distribution_factory,
        container_bindings,
    ):
        """Create class-wide variables.

        1. Create a repository.
        2. Create a remote pointing to external registry.
        3. Sync the repository using the remote and re-read the repo data.
        4. Create a container distribution to serve the repository
        5. Create another container distribution to the serve the repository version
        """
        repo = container_repository_factory()
        remote = container_remote_factory()
        container_sync(repo, remote)
        repo = container_bindings.RepositoriesContainerApi.read(repo.pulp_href)
        distribution_with_repo = container_distribution_factory(repository=repo.pulp_href)
        distribution_with_repo_version = container_distribution_factory(
            repository_version=repo.latest_version_href
        )
        return repo, distribution_with_repo, distribution_with_repo_version

    def test_api_returns_same_checksum(self, container_bindings, setup):
        """Verify that pulp serves image with the same checksum of remote.

        1. Call pulp repository API and get the content_summary for repo.
        2. Call dockerhub API and get blobsums for synced image.
        3. Compare the checksums.
        """
        # Get local checksums for content synced from the remote registry
        repo, _, _ = setup
        blobs = container_bindings.ContentBlobsApi.list(repository_version=repo.latest_version_href)
        blob_checksums = {c.digest for c in blobs.results}

        # Assert that at least one layer is synced from remote:latest
        # and the checksum matched with remote
        assert any(
            [checksum in blob_checksums for checksum in get_blobsums_from_remote_registry()]
        ), "Cannot find a matching layer on remote registry."

    def test_api_performes_schema_conversion(self, bindings_cfg, full_path, setup):
        """Verify pull via token with accepted content type."""
        _, distribution_with_repo, _ = setup
        image_path = "/v2/{}/manifests/{}".format(full_path(distribution_with_repo), "latest")
        latest_image_url = urljoin(bindings_cfg.host, image_path)

        auth = get_auth_for_url(latest_image_url)
        content_response = requests.get(
            latest_image_url, auth=auth, headers={"Accept": MEDIA_TYPE.MANIFEST_V1}
        )
        # I don't understand what this is testing
        assert 400 <= content_response.status_code < 500

    def test_create_empty_blob_on_the_fly(self, bindings_cfg, full_path, setup):
        """
        Test if empty blob getscreated and served on the fly.
        """
        _, distribution_with_repo, _ = setup
        blob_path = "/v2/{}/blobs/{}".format(full_path(distribution_with_repo), EMPTY_BLOB)
        empty_blob_url = urljoin(bindings_cfg.host, blob_path)

        auth = get_auth_for_url(empty_blob_url)
        content_response = requests.get(empty_blob_url, auth=auth)
        content_response.raise_for_status()
        # calculate digest of the payload
        digest = hashlib.sha256(content_response.content).hexdigest()
        # compare with the digest returned in the response header
        header_digest = content_response.headers["docker-content-digest"].split(":")[1]
        assert digest == header_digest

    def test_pull_image_from_repository(self, local_registry, registry_client, full_path, setup):
        """Verify that a client can pull the image from Pulp.

        1. Using the RegistryClient pull the image from Pulp.
        2. Pull the same image from remote registry.
        3. Verify both images has the same checksum.
        4. Ensure image is deleted after the test.
        """
        _, distribution_with_repo, _ = setup
        local_registry.pull(full_path(distribution_with_repo))
        local_image = local_registry.inspect(full_path(distribution_with_repo))

        registry_client.pull(REGISTRY_V2_REPO_HELLO_WORLD)
        remote_image = registry_client.inspect(REGISTRY_V2_REPO_HELLO_WORLD)

        registry_client.rmi(REGISTRY_V2_REPO_HELLO_WORLD)
        assert local_image[0]["Id"] == remote_image[0]["Id"]

    def test_pull_image_from_repository_version(
        self, local_registry, registry_client, full_path, setup
    ):
        """Verify that a client can pull the image from Pulp.

        1. Using the RegistryClient pull the image from Pulp.
        2. Pull the same image from remote registry.
        3. Verify both images has the same checksum.
        4. Ensure image is deleted after the test.
        """
        _, _, distribution_with_repo_version = setup
        local_registry.pull(full_path(distribution_with_repo_version))
        local_image = local_registry.inspect(full_path(distribution_with_repo_version))

        registry_client.pull(REGISTRY_V2_REPO_HELLO_WORLD)
        remote_image = registry_client.inspect(REGISTRY_V2_REPO_HELLO_WORLD)

        registry_client.rmi(REGISTRY_V2_REPO_HELLO_WORLD)
        assert local_image[0]["Id"] == remote_image[0]["Id"]

    def test_pull_image_with_tag(self, local_registry, registry_client, full_path, setup):
        """Verify that a client can pull the image from Pulp with a tag.

        1. Using the RegistryClient pull the image from Pulp specifying a tag.
        2. Pull the same image and same tag from remote registry.
        3. Verify both images has the same checksum.
        4. Ensure image is deleted after the test.
        """
        _, distribution_with_repo, _ = setup
        local_registry.pull(full_path(distribution_with_repo) + PULP_HELLO_WORLD_LINUX_TAG)
        local_image = local_registry.inspect(
            full_path(distribution_with_repo) + PULP_HELLO_WORLD_LINUX_TAG
        )

        registry_client.pull(REGISTRY_V2_REPO_HELLO_WORLD + PULP_HELLO_WORLD_LINUX_TAG)
        remote_image = registry_client.inspect(
            REGISTRY_V2_REPO_HELLO_WORLD + PULP_HELLO_WORLD_LINUX_TAG
        )

        registry_client.rmi(REGISTRY_V2_REPO_HELLO_WORLD + PULP_HELLO_WORLD_LINUX_TAG)
        assert local_image[0]["Id"] == remote_image[0]["Id"]

    def test_pull_nonexistent_image(self, local_registry, full_path):
        """Verify that a client cannot pull nonexistent image from Pulp.

        1. Using the RegistryClient try to pull nonexistent image from Pulp.
        2. Assert that error is occurred and nothing has been pulled.
        """
        with pytest.raises(subprocess.CalledProcessError):
            local_registry.pull(full_path("inexistentimagename"))

    def test_pull_nonexistent_blob(self, bindings_cfg, full_path, setup):
        """
        Verify that a GET request to a nonexistent BLOB will be properly handled
        instead of outputting a stacktrace.
        """
        _, distribution_with_repo, _ = setup
        blob_path = "/v2/{}/blobs/{}".format(full_path(distribution_with_repo), EMPTY_JSON)
        non_existing_blob_url = urljoin(bindings_cfg.host, blob_path)

        auth = get_auth_for_url(non_existing_blob_url)
        content_response = requests.get(non_existing_blob_url, auth=auth)
        assert content_response.status_code == 404


class TestPullOnDemandContent:
    """Verify whether on-demand served images by Pulp can be pulled."""

    @pytest.fixture(scope="class")
    def setup(
        self,
        container_repository_factory,
        container_remote_factory,
        container_sync,
        container_distribution_factory,
        pulpcore_bindings,
        container_bindings,
        registry_client,
        monitor_task,
    ):
        """Create class-wide variables and delete orphans.

        1. Create a repository.
        2. Create a remote pointing to external registry with policy=on_demand.
        3. Sync the repository using the remote and re-read the repo data.
        4. Create a container distribution to serve the repository
        5. Create another container distribution to the serve the repository version
        """
        monitor_task(
            pulpcore_bindings.OrphansCleanupApi.cleanup({"orphan_protection_time": 0}).task
        )
        registry_client.rmi("-a", "-f")
        repo = container_repository_factory()
        remote = container_remote_factory(policy="on_demand")
        container_sync(repo, remote)
        repo = container_bindings.RepositoriesContainerApi.read(repo.pulp_href)
        distribution_with_repo = container_distribution_factory(repository=repo.pulp_href)
        distribution_with_repo_version = container_distribution_factory(
            repository_version=repo.latest_version_href
        )
        artifact_count = pulpcore_bindings.ArtifactsApi.list().count
        return repo, distribution_with_repo, distribution_with_repo_version, artifact_count

    def test_api_returns_same_checksum(self, container_bindings, setup):
        """Verify that pulp serves image with the same checksum of remote.

        1. Call pulp repository API and get the content_summary for repo.
        2. Call dockerhub API and get blobsums for synced image.
        3. Compare the checksums.
        """
        # Get local checksums for content synced from remote registy
        repo, _, _, _ = setup
        blobs = container_bindings.ContentBlobsApi.list(repository_version=repo.latest_version_href)
        blob_checksums = {c.digest for c in blobs.results}

        # Assert that at least one layer is synced from remote:latest
        # and the checksum matched with remote
        assert any(
            [checksum in blob_checksums for checksum in get_blobsums_from_remote_registry()]
        ), "Cannot find a matching layer on remote registry."

    def test_pull_image_from_repository(
        self, local_registry, registry_client, pulpcore_bindings, full_path, setup
    ):
        """Verify that a client can pull the image from Pulp (on-demand).

        1. Using the RegistryClient pull the image from Pulp.
        2. Pull the same image from remote registry.
        3. Verify both images has the same checksum.
        4. Verify that the number of artifacts in Pulp has increased.
        5. Ensure image is deleted after the test.
        """
        _, distribution_with_repo, _, artifact_count = setup
        local_registry.pull(full_path(distribution_with_repo))
        local_image = local_registry.inspect(full_path(distribution_with_repo))
        registry_client.rmi(local_image[0]["Id"])

        registry_client.pull(REGISTRY_V2_REPO_HELLO_WORLD)
        remote_image = registry_client.inspect(REGISTRY_V2_REPO_HELLO_WORLD)

        registry_client.rmi(REGISTRY_V2_REPO_HELLO_WORLD)
        assert local_image[0]["Id"] == remote_image[0]["Id"]

        new_artifact_count = pulpcore_bindings.ArtifactsApi.list().count
        assert new_artifact_count > artifact_count

    def test_pull_image_from_repository_version(
        self, local_registry, registry_client, full_path, setup
    ):
        """Verify that a client can pull the image from Pulp (on-demand).

        1. Using the RegistryClient pull the image from Pulp.
        2. Pull the same image from remote registry.
        3. Verify both images has the same checksum.
        4. Ensure image is deleted after the test.
        """
        _, _, distribution_with_repo_version, _ = setup
        local_registry.pull(full_path(distribution_with_repo_version))
        local_image = local_registry.inspect(full_path(distribution_with_repo_version))
        registry_client.rmi(local_image[0]["Id"])

        registry_client.pull(REGISTRY_V2_REPO_HELLO_WORLD)
        remote_image = registry_client.inspect(REGISTRY_V2_REPO_HELLO_WORLD)

        registry_client.rmi(REGISTRY_V2_REPO_HELLO_WORLD)
        assert local_image[0]["Id"] == remote_image[0]["Id"]

    def test_pull_image_with_tag(self, local_registry, registry_client, full_path, setup):
        """Verify that a client can pull the image from Pulp with a tag (on-demand).

        1. Using the RegistryClient pull the image from Pulp specifying a tag.
        2. Pull the same image and same tag from remote registry.
        3. Verify both images has the same checksum.
        4. Ensure image is deleted after the test.
        """
        _, distribution_with_repo, _, _ = setup
        local_registry.pull(full_path(distribution_with_repo) + PULP_HELLO_WORLD_LINUX_TAG)
        local_image = local_registry.inspect(
            full_path(distribution_with_repo) + PULP_HELLO_WORLD_LINUX_TAG
        )
        registry_client.rmi(local_image[0]["Id"])

        registry_client.pull(REGISTRY_V2_REPO_HELLO_WORLD + PULP_HELLO_WORLD_LINUX_TAG)
        remote_image = registry_client.inspect(
            REGISTRY_V2_REPO_HELLO_WORLD + PULP_HELLO_WORLD_LINUX_TAG
        )

        registry_client.rmi(REGISTRY_V2_REPO_HELLO_WORLD + PULP_HELLO_WORLD_LINUX_TAG)
        assert local_image[0]["Id"] == remote_image[0]["Id"]

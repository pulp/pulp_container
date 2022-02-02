# coding=utf-8
"""Tests that verify that images served by Pulp can be pulled."""
import contextlib
import hashlib
import json
import requests
import unittest
from urllib.parse import urljoin, urlparse

from pulp_smash import api, cli, config, exceptions
from pulp_smash.pulp3.bindings import delete_orphans, monitor_task
from pulp_smash.pulp3.utils import (
    get_content,
    gen_distribution,
    gen_repo,
)

from pulp_container.tests.functional.utils import (
    TOKEN_AUTH_DISABLED,
    core_client,
    gen_container_client,
    gen_container_remote,
    get_blobsums_from_remote_registry,
    BearerTokenAuth,
    AuthenticationHeaderQueries,
)
from pulp_container.tests.functional.constants import (
    CONTAINER_CONTENT_NAME,
    REGISTRY_V2_REPO_HELLO_WORLD,
    PULP_HELLO_WORLD_LINUX_TAG,
)
from pulp_container.constants import EMPTY_BLOB, MEDIA_TYPE

from pulpcore.client.pulp_container import (
    ContainerContainerDistribution,
    ContainerContainerRepository,
    DistributionsContainerApi,
    RepositorySyncURL,
    RepositoriesContainerApi,
    RemotesContainerApi,
)
from pulpcore.client.pulpcore import ArtifactsApi


class PullContentTestCase(unittest.TestCase):
    """Verify whether images served by Pulp can be pulled."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables.

        1. Create a repository.
        2. Create a remote pointing to external registry.
        3. Sync the repository using the remote and re-read the repo data.
        4. Create a container distribution to serve the repository
        5. Create another container distribution to the serve the repository version

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

        cls.teardown_cleanups = []

        delete_orphans()

        with contextlib.ExitStack() as stack:
            # ensure tearDownClass runs if an error occurs here
            stack.callback(cls.tearDownClass)

            # Step 1
            _repo = cls.repositories_api.create(ContainerContainerRepository(**gen_repo()))
            cls.teardown_cleanups.append((cls.repositories_api.delete, _repo.pulp_href))

            # Step 2
            cls.remote = cls.remotes_api.create(gen_container_remote())
            cls.teardown_cleanups.append((cls.remotes_api.delete, cls.remote.pulp_href))

            # Step 3
            sync_data = RepositorySyncURL(remote=cls.remote.pulp_href)
            sync_response = cls.repositories_api.sync(_repo.pulp_href, sync_data)
            monitor_task(sync_response.task)
            cls.repo = cls.repositories_api.read(_repo.pulp_href)

            # Step 4.
            distribution_response = cls.distributions_api.create(
                ContainerContainerDistribution(**gen_distribution(repository=cls.repo.pulp_href))
            )
            created_resources = monitor_task(distribution_response.task).created_resources
            distribution = cls.distributions_api.read(created_resources[0])
            cls.distribution_with_repo = cls.distributions_api.read(distribution.pulp_href)
            cls.teardown_cleanups.append(
                (cls.distributions_api.delete, cls.distribution_with_repo.pulp_href)
            )

            # Step 5.
            distribution_response = cls.distributions_api.create(
                ContainerContainerDistribution(
                    **gen_distribution(repository_version=cls.repo.latest_version_href)
                )
            )
            created_resources = monitor_task(distribution_response.task).created_resources
            distribution = cls.distributions_api.read(created_resources[0])
            cls.distribution_with_repo_version = cls.distributions_api.read(distribution.pulp_href)
            cls.teardown_cleanups.append(
                (cls.distributions_api.delete, cls.distribution_with_repo_version.pulp_href)
            )

            # remove callback if everything goes well
            stack.pop_all()

    @classmethod
    def tearDownClass(cls):
        """Clean class-wide variable."""
        for cleanup_function, args in reversed(cls.teardown_cleanups):
            cleanup_function(args)

    def test_api_returns_same_checksum(self):
        """Verify that pulp serves image with the same checksum of remote.

        1. Call pulp repository API and get the content_summary for repo.
        2. Call dockerhub API and get blobsums for synced image.
        3. Compare the checksums.
        """
        # Get local checksums for content synced from the remote registry
        checksums = [
            content["digest"]
            for content in get_content(self.repo.to_dict())[CONTAINER_CONTENT_NAME]
        ]

        # Assert that at least one layer is synced from remote:latest
        # and the checksum matched with remote
        self.assertTrue(
            any([checksum in checksums for checksum in get_blobsums_from_remote_registry()]),
            "Cannot find a matching layer on remote registry.",
        )

    def test_api_performes_schema_conversion(self):
        """Verify pull via token with accepted content type."""
        image_path = "/v2/{}/manifests/{}".format(self.distribution_with_repo.base_path, "latest")
        latest_image_url = urljoin(self.cfg.get_base_url(), image_path)

        if TOKEN_AUTH_DISABLED:
            auth = ()
        else:
            with self.assertRaises(requests.HTTPError) as cm:
                self.client.get(latest_image_url, headers={"Accept": MEDIA_TYPE.MANIFEST_V1})

            content_response = cm.exception.response
            self.assertEqual(content_response.status_code, 401)

            authenticate_header = content_response.headers["Www-Authenticate"]
            queries = AuthenticationHeaderQueries(authenticate_header)
            content_response = requests.get(
                queries.realm, params={"service": queries.service, "scope": queries.scope}
            )
            content_response.raise_for_status()
            token = content_response.json()["token"]
            auth = BearerTokenAuth(token)
        content_response = requests.get(
            latest_image_url,
            auth=auth,
            headers={"Accept": MEDIA_TYPE.MANIFEST_V1},
        )
        content_response.raise_for_status()
        base_content_type = content_response.headers["Content-Type"].split(";")[0]
        self.assertIn(base_content_type, {MEDIA_TYPE.MANIFEST_V1, MEDIA_TYPE.MANIFEST_V1_SIGNED})

        header_digest = content_response.headers["Docker-Content-Digest"]
        converted_manifest = json.loads(content_response.content)
        converted_manifest.pop("signatures")
        manifest_string = json.dumps(
            converted_manifest, indent=3, sort_keys=True, separators=(",", ": ")
        ).encode("utf-8")
        # the header digest should be equal to the SHA256 hash computed from
        # a manifest without signatures
        computed_digest = hashlib.sha256(manifest_string).hexdigest()
        self.assertEqual(
            computed_digest, header_digest.split(":")[1], "The manifest digests are not equal"
        )

    def test_create_empty_blob_on_the_fly(self):
        """
        Test if empty blob getscreated and served on the fly.
        """
        blob_path = "/v2/{}/blobs/{}".format(self.distribution_with_repo.base_path, EMPTY_BLOB)
        empty_blob_url = urljoin(self.cfg.get_base_url(), blob_path)

        if TOKEN_AUTH_DISABLED:
            auth = ()
        else:
            with self.assertRaises(requests.HTTPError) as cm:
                requests.get(empty_blob_url).raise_for_status()

            content_response = cm.exception.response
            self.assertEqual(content_response.status_code, 401)

            authenticate_header = content_response.headers["Www-Authenticate"]
            queries = AuthenticationHeaderQueries(authenticate_header)
            content_response = requests.get(
                queries.realm, params={"service": queries.service, "scope": queries.scope}
            )
            content_response.raise_for_status()
            auth = BearerTokenAuth(content_response.json()["token"])
        content_response = requests.get(empty_blob_url, auth=auth)
        content_response.raise_for_status()
        # calculate digest of the payload
        digest = hashlib.sha256(content_response.content).hexdigest()
        # compare with the digest returned in the response header
        header_digest = content_response.headers["docker-content-digest"].split(":")[1]
        self.assertEqual(digest, header_digest)

    def test_pull_image_from_repository(self):
        """Verify that a client can pull the image from Pulp.

        1. Using the RegistryClient pull the image from Pulp.
        2. Pull the same image from remote registry.
        3. Verify both images has the same checksum.
        4. Ensure image is deleted after the test.
        """
        registry = cli.RegistryClient(self.cfg)
        registry.raise_if_unsupported(unittest.SkipTest, "Test requires podman/docker")
        registry.login("-u", "admin", "-p", "password", self.registry_name)

        local_url = urljoin(self.cfg.get_base_url(), self.distribution_with_repo.base_path)

        registry.pull(local_url)
        self.teardown_cleanups.append((registry.rmi, local_url))
        local_image = registry.inspect(local_url)

        registry.pull(REGISTRY_V2_REPO_HELLO_WORLD)
        remote_image = registry.inspect(REGISTRY_V2_REPO_HELLO_WORLD)

        self.assertEqual(local_image[0]["Id"], remote_image[0]["Id"])
        registry.rmi(REGISTRY_V2_REPO_HELLO_WORLD)

    def test_pull_image_from_repository_version(self):
        """Verify that a client can pull the image from Pulp.

        1. Using the RegistryClient pull the image from Pulp.
        2. Pull the same image from remote registry.
        3. Verify both images has the same checksum.
        4. Ensure image is deleted after the test.
        """
        registry = cli.RegistryClient(self.cfg)
        registry.raise_if_unsupported(unittest.SkipTest, "Test requires podman/docker")
        registry.login("-u", "admin", "-p", "password", self.registry_name)

        local_url = urljoin(self.cfg.get_base_url(), self.distribution_with_repo_version.base_path)

        registry.pull(local_url)
        self.teardown_cleanups.append((registry.rmi, local_url))
        local_image = registry.inspect(local_url)

        registry.pull(REGISTRY_V2_REPO_HELLO_WORLD)
        remote_image = registry.inspect(REGISTRY_V2_REPO_HELLO_WORLD)

        self.assertEqual(local_image[0]["Id"], remote_image[0]["Id"])
        registry.rmi(REGISTRY_V2_REPO_HELLO_WORLD)

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
        self.teardown_cleanups.append((registry.rmi, local_url))
        local_image = registry.inspect(local_url)

        registry.pull(REGISTRY_V2_REPO_HELLO_WORLD + PULP_HELLO_WORLD_LINUX_TAG)
        self.teardown_cleanups.append(
            (registry.rmi, REGISTRY_V2_REPO_HELLO_WORLD + PULP_HELLO_WORLD_LINUX_TAG)
        )
        remote_image = registry.inspect(REGISTRY_V2_REPO_HELLO_WORLD + PULP_HELLO_WORLD_LINUX_TAG)

        self.assertEqual(local_image[0]["Id"], remote_image[0]["Id"])

    def test_pull_nonexistent_image(self):
        """Verify that a client cannot pull nonexistent image from Pulp.

        1. Using the RegistryClient try to pull nonexistent image from Pulp.
        2. Assert that error is occurred and nothing has been pulled.
        """
        registry = cli.RegistryClient(self.cfg)
        registry.raise_if_unsupported(unittest.SkipTest, "Test requires podman/docker")
        registry.login("-u", "admin", "-p", "password", self.registry_name)

        local_url = urljoin(self.cfg.get_base_url(), "inexistentimagename")
        with self.assertRaises(exceptions.CalledProcessError):
            registry.pull(local_url)


class PullOnDemandContentTestCase(unittest.TestCase):
    """Verify whether on-demand served images by Pulp can be pulled."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables and delete orphans.

        1. Create a repository.
        2. Create a remote pointing to external registry with policy=on_demand.
        3. Sync the repository using the remote and re-read the repo data.
        4. Create a container distribution to serve the repository
        5. Create another container distribution to the serve the repository version

        This tests targets the following issue:

        * `Pulp #4460 <https://pulp.plan.io/issues/4460>`_
        """
        cls.cfg = config.get_config()
        cls.registry_name = urlparse(cls.cfg.get_base_url()).netloc

        client_api = gen_container_client()
        cls.repositories_api = RepositoriesContainerApi(client_api)
        cls.remotes_api = RemotesContainerApi(client_api)
        cls.distributions_api = DistributionsContainerApi(client_api)

        cls.teardown_cleanups = []

        delete_orphans()

        with contextlib.ExitStack() as stack:
            # ensure tearDownClass runs if an error occurs here
            stack.callback(cls.tearDownClass)

            # Step 1
            _repo = cls.repositories_api.create(ContainerContainerRepository(**gen_repo()))
            cls.teardown_cleanups.append((cls.repositories_api.delete, _repo.pulp_href))

            # Step 2
            cls.remote = cls.remotes_api.create(gen_container_remote(policy="on_demand"))
            cls.teardown_cleanups.append((cls.remotes_api.delete, cls.remote.pulp_href))

            # Step 3
            sync_data = RepositorySyncURL(remote=cls.remote.pulp_href)
            sync_response = cls.repositories_api.sync(_repo.pulp_href, sync_data)
            monitor_task(sync_response.task)

            cls.repo = cls.repositories_api.read(_repo.pulp_href)
            cls.artifacts_api = ArtifactsApi(core_client)
            cls.artifact_count = cls.artifacts_api.list().count

            # Step 4.
            distribution_response = cls.distributions_api.create(
                ContainerContainerDistribution(**gen_distribution(repository=cls.repo.pulp_href))
            )
            created_resources = monitor_task(distribution_response.task).created_resources

            distribution = cls.distributions_api.read(created_resources[0])
            cls.distribution_with_repo = cls.distributions_api.read(distribution.pulp_href)
            cls.teardown_cleanups.append(
                (cls.distributions_api.delete, cls.distribution_with_repo.pulp_href)
            )

            # Step 5.
            distribution_response = cls.distributions_api.create(
                ContainerContainerDistribution(
                    **gen_distribution(repository_version=cls.repo.latest_version_href)
                )
            )
            created_resources = monitor_task(distribution_response.task).created_resources
            distribution = cls.distributions_api.read(created_resources[0])
            cls.distribution_with_repo_version = cls.distributions_api.read(distribution.pulp_href)
            cls.teardown_cleanups.append(
                (cls.distributions_api.delete, cls.distribution_with_repo_version.pulp_href)
            )

            # remove callback if everything goes well
            stack.pop_all()

    @classmethod
    def tearDownClass(cls):
        """Clean class-wide variable."""
        for cleanup_function, args in reversed(cls.teardown_cleanups):
            cleanup_function(args)

    def test_api_returns_same_checksum(self):
        """Verify that pulp serves image with the same checksum of remote.

        1. Call pulp repository API and get the content_summary for repo.
        2. Call dockerhub API and get blobsums for synced image.
        3. Compare the checksums.
        """
        # Get local checksums for content synced from remote registy
        checksums = [
            content["digest"]
            for content in get_content(self.repo.to_dict())[CONTAINER_CONTENT_NAME]
        ]

        # Assert that at least one layer is synced from remote:latest
        # and the checksum matched with remote
        self.assertTrue(
            any([checksum in checksums for checksum in get_blobsums_from_remote_registry()]),
            "Cannot find a matching layer on remote registry.",
        )

    def test_pull_image_from_repository(self):
        """Verify that a client can pull the image from Pulp (on-demand).

        1. Using the RegistryClient pull the image from Pulp.
        2. Pull the same image from remote registry.
        3. Verify both images has the same checksum.
        4. Verify that the number of artifacts in Pulp has increased.
        5. Ensure image is deleted after the test.
        """
        registry = cli.RegistryClient(self.cfg)
        registry.raise_if_unsupported(unittest.SkipTest, "Test requires podman/docker")
        registry.login("-u", "admin", "-p", "password", self.registry_name)

        local_url = urljoin(self.cfg.get_base_url(), self.distribution_with_repo.base_path)

        registry.pull(local_url)
        self.teardown_cleanups.append((registry.rmi, local_url))
        local_image = registry.inspect(local_url)

        registry.pull(REGISTRY_V2_REPO_HELLO_WORLD)
        remote_image = registry.inspect(REGISTRY_V2_REPO_HELLO_WORLD)

        self.assertEqual(local_image[0]["Id"], remote_image[0]["Id"])

        new_artifact_count = self.artifacts_api.list().count
        self.assertGreater(new_artifact_count, self.artifact_count)

        registry.rmi(REGISTRY_V2_REPO_HELLO_WORLD)

    def test_pull_image_from_repository_version(self):
        """Verify that a client can pull the image from Pulp (on-demand).

        1. Using the RegistryClient pull the image from Pulp.
        2. Pull the same image from remote registry.
        3. Verify both images has the same checksum.
        4. Ensure image is deleted after the test.
        """
        registry = cli.RegistryClient(self.cfg)
        registry.raise_if_unsupported(unittest.SkipTest, "Test requires podman/docker")
        registry.login("-u", "admin", "-p", "password", self.registry_name)

        local_url = urljoin(self.cfg.get_base_url(), self.distribution_with_repo_version.base_path)

        registry.pull(local_url)
        self.teardown_cleanups.append((registry.rmi, local_url))
        local_image = registry.inspect(local_url)

        registry.pull(REGISTRY_V2_REPO_HELLO_WORLD)
        remote_image = registry.inspect(REGISTRY_V2_REPO_HELLO_WORLD)

        self.assertEqual(local_image[0]["Id"], remote_image[0]["Id"])
        registry.rmi(REGISTRY_V2_REPO_HELLO_WORLD)

    def test_pull_image_with_tag(self):
        """Verify that a client can pull the image from Pulp with a tag (on-demand).

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
        self.teardown_cleanups.append((registry.rmi, local_url))
        local_image = registry.inspect(local_url)

        registry.pull(REGISTRY_V2_REPO_HELLO_WORLD + PULP_HELLO_WORLD_LINUX_TAG)
        self.teardown_cleanups.append(
            (registry.rmi, REGISTRY_V2_REPO_HELLO_WORLD + PULP_HELLO_WORLD_LINUX_TAG)
        )
        remote_image = registry.inspect(REGISTRY_V2_REPO_HELLO_WORLD + PULP_HELLO_WORLD_LINUX_TAG)

        self.assertEqual(local_image[0]["Id"], remote_image[0]["Id"])

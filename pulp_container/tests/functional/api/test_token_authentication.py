# coding=utf-8
"""Tests for token authentication."""
import unittest

from urllib.parse import urljoin
from requests.exceptions import HTTPError

from pulp_smash import api, config, cli
from pulp_smash.pulp3.utils import gen_repo, gen_distribution

from pulp_container.tests.functional.utils import (
    gen_container_remote,
    gen_container_client,
    gen_token_signing_keys,
    monitor_task,
    BearerTokenAuth,
)
from pulp_container.tests.functional.constants import (
    CONTAINER_TAG_PATH,
    DOCKERHUB_PULP_FIXTURE_1,
)
from pulp_container.constants import MEDIA_TYPE

from pulpcore.client.pulp_container import (
    ContainerContainerDistribution,
    ContainerContainerRepository,
    ContainerContainerRemote,
    DistributionsContainerApi,
    RepositoriesContainerApi,
    RemotesContainerApi,
    RepositorySyncURL,
)


class TokenAuthenticationTestCase(unittest.TestCase):
    """
    A test case for authenticating users via Bearer token.

    This tests targets the following issue:

    * `Pulp #4938 <https://pulp.plan.io/issues/4938>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class wide-variables."""
        cls.cfg = config.get_config()
        gen_token_signing_keys(cls.cfg)
        cls.client = api.Client(cls.cfg, api.page_handler)

        api_client = gen_container_client()
        cls.repositories_api = RepositoriesContainerApi(api_client)
        cls.remotes_api = RemotesContainerApi(api_client)
        cls.distributions_api = DistributionsContainerApi(api_client)

        cls.repository = cls.repositories_api.create(ContainerContainerRepository(**gen_repo()))

        remote_data = gen_container_remote(upstream_name=DOCKERHUB_PULP_FIXTURE_1)
        cls.remote = cls.remotes_api.create(ContainerContainerRemote(**remote_data))

        sync_data = RepositorySyncURL(remote=cls.remote.pulp_href)
        sync_response = cls.repositories_api.sync(cls.repository.pulp_href, sync_data)
        monitor_task(sync_response.task)

        distribution_data = gen_distribution(repository=cls.repository.pulp_href)
        distribution_response = cls.distributions_api.create(
            ContainerContainerDistribution(**distribution_data)
        )
        created_resources = monitor_task(distribution_response.task)
        cls.distribution = cls.distributions_api.read(created_resources[0])

    @classmethod
    def tearDownClass(cls):
        """Clean generated resources."""
        cls.repositories_api.delete(cls.repository.pulp_href)
        cls.remotes_api.delete(cls.remote.pulp_href)
        cls.distributions_api.delete(cls.distribution.pulp_href)

    def test_pull_image_with_raw_http_requests(self):
        """
        Test if a content was pulled from a registry by using raw HTTP requests.

        The registry offers a reference to a certified authority which generates a
        Bearer token. The generated Bearer token is afterwards used to pull the image.
        All requests are sent via aiohttp modules.
        """
        image_path = "/v2/{}/manifests/{}".format(self.distribution.base_path, "manifest_a")
        latest_image_url = urljoin(self.cfg.get_content_host_base_url(), image_path)

        with self.assertRaises(HTTPError) as cm:
            self.client.get(latest_image_url, headers={"Accept": MEDIA_TYPE.MANIFEST_V2})

        content_response = cm.exception.response
        self.assertEqual(content_response.status_code, 401)

        authenticate_header = content_response.headers["Www-Authenticate"]
        queries = AuthenticationHeaderQueries(authenticate_header)
        content_response = self.client.get(
            queries.realm,
            params={"service": queries.service, "scope": queries.scope}
        )
        content_response = self.client.get(
            latest_image_url,
            auth=BearerTokenAuth(content_response["token"]),
            headers={"Accept": MEDIA_TYPE.MANIFEST_V2}
        )
        self.compare_config_blob_digests(content_response["config"]["digest"])

    def test_pull_image_with_real_container_client(self):
        """
        Test if a CLI client is able to pull an image from an authenticated registry.

        This test checks if ordinary clients, like docker, or podman, are able to pull the
        image from a secured registry.
        """
        registry = cli.RegistryClient(self.cfg)
        registry.raise_if_unsupported(unittest.SkipTest, "Test requires podman/docker")

        image_url = urljoin(
            self.cfg.get_content_host_base_url(),
            self.distribution.base_path
        )
        image_with_tag = f"{image_url}:manifest_a"
        registry.pull(image_with_tag)

        image = registry.inspect(image_with_tag)

        # The docker client returns a different Id compared to an Id returned by the podman client.
        # 'Id': 'sha256:d21d863f69b5de1a973a41344488f2ec89a625f2624195f51b4e2d54a97fc53b' (docker)
        # 'Id': 'd21d863f69b5de1a973a41344488f2ec89a625f2624195f51b4e2d54a97fc53b' (podman)
        # As long as the output differs in this manner, it is necessary to prepend the string
        # 'sha256:' to the fetched digest.
        image_id = image[0]["Id"]
        if image_id.startswith("sha256:"):
            image_digest = image_id
        else:
            image_digest = "sha256:" + image_id

        self.compare_config_blob_digests(image_digest)

    def compare_config_blob_digests(self, pulled_manifest_digest):
        """Check if a valid config was pulled from a registry."""
        tags_by_name_url = f"{CONTAINER_TAG_PATH}?name=manifest_a"
        tag_response = self.client.get(tags_by_name_url)

        tagged_manifest_href = tag_response[0]["tagged_manifest"]
        manifest_response = self.client.get(tagged_manifest_href)

        config_blob_response = self.client.get(manifest_response["config_blob"])
        self.assertEqual(pulled_manifest_digest, config_blob_response["digest"])


class AuthenticationHeaderQueries:
    """A data class to store header queries located in the Www-Authenticate header."""

    def __init__(self, authenticate_header):
        """Extract service, realm, and scope from the header."""
        realm, service, scope = authenticate_header[7:].split(",")
        # realm="rlm" -> rlm
        self.realm = realm[6:][1:-1]
        # service="srv" -> srv
        self.service = service[8:][1:-1]
        # scope="scp" -> scp
        self.scope = scope[6:][1:-1]

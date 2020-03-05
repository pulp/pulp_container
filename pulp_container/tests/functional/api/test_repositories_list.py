# coding=utf-8
"""Tests for fetching the list of all repositories."""
import unittest

from urllib.parse import urljoin
from requests.exceptions import HTTPError

from pulp_smash import api, config
from pulp_smash.pulp3.utils import gen_distribution, gen_repo

from pulp_container.tests.functional.constants import DOCKERHUB_PULP_FIXTURE_1

from pulp_container.tests.functional.utils import (
    gen_container_remote,
    gen_container_client,
    gen_token_signing_keys,
    monitor_task,
    BearerTokenAuth,
)

from pulpcore.client.pulp_container import (
    ContainerContainerRepository,
    ContainerContainerDistribution,
    ContainerContainerRemote,
    DistributionsContainerApi,
    RepositoriesContainerApi,
    RemotesContainerApi,
    RepositorySyncURL,
)


class RepositoriesListTestCase(unittest.TestCase):
    """Test case for listing all repositories within a registry."""

    @classmethod
    def setUpClass(cls):
        """Create class wide-variables."""
        api_client = gen_container_client()
        cls.repositories_api = RepositoriesContainerApi(api_client)
        cls.remotes_api = RemotesContainerApi(api_client)
        cls.distributions_api = DistributionsContainerApi(api_client)

        cls.cfg = config.get_config()
        gen_token_signing_keys(cls.cfg)
        cls.client = api.Client(cls.cfg, api.json_handler)

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
        cls.distribution1 = cls.distributions_api.read(created_resources[0])

        distribution_data = gen_distribution(repository=cls.repository.pulp_href)
        distribution_response = cls.distributions_api.create(
            ContainerContainerDistribution(**distribution_data)
        )
        created_resources = monitor_task(distribution_response.task)
        cls.distribution2 = cls.distributions_api.read(created_resources[0])

    @classmethod
    def tearDownClass(cls):
        """Clean generated resources."""
        cls.repositories_api.delete(cls.repository.pulp_href)
        cls.remotes_api.delete(cls.remote.pulp_href)

        cls.distributions_api.delete(cls.distribution1.pulp_href)
        cls.distributions_api.delete(cls.distribution2.pulp_href)

    def test_listing_repositories(self):
        """
        Check if the registry correctly returns all generated repositories' names.

        In this test, it is also required to obtain a Bearer token. Because of that, there is
        caught an exception for the HTTP 401 response at first. Then, the token is retrieved
        from the token server and is used for requesting the list of repositories again.
        """
        repositories_list_endpoint = urljoin(self.cfg.get_content_host_base_url(), "/v2/_catalog")

        with self.assertRaises(HTTPError) as cm:
            self.client.get(repositories_list_endpoint)
        content_response = cm.exception.response
        authenticate_header = content_response.headers["Www-Authenticate"]

        queries = AuthenticationHeaderQueries(authenticate_header)
        content_response = self.client.get(queries.realm, params={"service": queries.service})
        repositories = self.client.get(
            repositories_list_endpoint,
            auth=BearerTokenAuth(content_response["token"])
        )

        repositories_names = [self.distribution1.base_path, self.distribution2.base_path]
        self.assertEqual(repositories, {"repositories": repositories_names})


class AuthenticationHeaderQueries:
    """A data class to store header queries located in the Www-Authenticate header."""

    def __init__(self, authenticate_header):
        """
        Extract service and realm from the header.

        The scope is not provided by the token server because we are accessing the endpoint from
        the root.
        """
        realm, service = authenticate_header[7:].split(',')
        # realm="rlm" -> rlm
        self.realm = realm[6:][1:-1]
        # service="srv" -> srv
        self.service = service[8:][1:-1]

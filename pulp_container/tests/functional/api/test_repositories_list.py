# coding=utf-8
"""Tests for fetching the list of all repositories."""
import unittest

from urllib.parse import urljoin
from requests.exceptions import HTTPError

from pulp_smash import api, config, cli
from pulp_smash.pulp3.utils import gen_repo, sync, gen_distribution

from pulp_container.tests.functional.utils import set_up_module as setUpModule  # noqa:F401
from pulp_container.tests.functional.utils import gen_container_remote, BearerTokenAuth

from pulp_container.tests.functional.constants import (
    CONTAINER_DISTRIBUTION_PATH,
    CONTAINER_REMOTE_PATH,
    CONTAINER_REPO_PATH,
    DOCKERHUB_PULP_FIXTURE_1,
)


class RepositoriesListTestCase(unittest.TestCase):
    """Test case for listing all repositories within a registry."""

    @classmethod
    def setUpClass(cls):
        """Create class wide-variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)

        token_auth = cls.cfg.hosts[0].roles['token auth']
        client = cli.Client(cls.cfg)
        client.run('openssl ecparam -genkey -name prime256v1 -noout -out {}'
                   .format(token_auth['private key']).split())
        client.run('openssl ec -in {} -pubout -out {}'.format(
            token_auth['private key'], token_auth['public key']).split())

        cls.repository = cls.client.post(CONTAINER_REPO_PATH, gen_repo())
        remote_data = gen_container_remote(upstream_name=DOCKERHUB_PULP_FIXTURE_1)
        cls.remote = cls.client.post(CONTAINER_REMOTE_PATH, remote_data)
        sync(cls.cfg, cls.remote, cls.repository)

        cls.distribution1 = cls.client.using_handler(api.task_handler).post(
            CONTAINER_DISTRIBUTION_PATH,
            gen_distribution(repository=cls.repository['pulp_href'])
        )
        cls.distribution2 = cls.client.using_handler(api.task_handler).post(
            CONTAINER_DISTRIBUTION_PATH,
            gen_distribution(repository=cls.repository['pulp_href'])
        )

    @classmethod
    def tearDownClass(cls):
        """Clean generated resources."""
        cls.client.delete(cls.repository['pulp_href'])
        cls.client.delete(cls.remote['pulp_href'])

        cls.client.delete(cls.distribution1['pulp_href'])
        cls.client.delete(cls.distribution2['pulp_href'])

    def test_listing_repositories(self):
        """
        Check if the registry correctly returns all generated repositories' names.

        In this test, it is also required to obtain a Bearer token. Because of that, there is
        caught an exception for the HTTP 401 response at first. Then, the token is retrieved
        from the token server and is used for requesting the list of repositories again.
        """
        repositories_list_endpoint = urljoin(self.cfg.get_content_host_base_url(), '/v2/_catalog')

        with self.assertRaises(HTTPError) as cm:
            self.client.get(repositories_list_endpoint)
        content_response = cm.exception.response
        authenticate_header = content_response.headers['Www-Authenticate']

        queries = AuthenticationHeaderQueries(authenticate_header)
        content_response = self.client.get(queries.realm, params={'service': queries.service})
        repositories = self.client.get(
            repositories_list_endpoint,
            auth=BearerTokenAuth(content_response['token'])
        )

        repositories_names = [self.distribution1['base_path'], self.distribution2['base_path']]
        self.assertEqual(repositories, {'repositories': repositories_names})


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

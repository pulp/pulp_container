# coding=utf-8
"""Tests for token authentication."""
import unittest

from urllib.parse import urljoin
from requests.exceptions import HTTPError
from requests.auth import AuthBase

from pulp_smash import api, config, cli
from pulp_smash.pulp3.utils import gen_repo, sync, gen_distribution

from pulp_container.tests.functional.utils import set_up_module as setUpModule  # noqa:F401
from pulp_container.tests.functional.utils import gen_container_remote

from pulp_container.tests.functional.constants import (
    CONTAINER_TAG_PATH,
    CONTAINER_REMOTE_PATH,
    CONTAINER_REPO_PATH,
    CONTAINER_DISTRIBUTION_PATH,
    DOCKERHUB_PULP_FIXTURE_1,
)
from pulp_container.constants import MEDIA_TYPE


"""
@unittest.skip(
    "A handler for a token authentication relies on a provided token server's "
    "fully qualified domain name (TOKEN_SERVER) in the file /etc/pulp/settings.py; "
    "therefore, it is necessary to check if TOKEN_SERVER was specified; otherwise, "
    "these tests are no longer valid because the token authentication is turned off "
    "by default."
)
"""


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

        token_auth = cls.cfg.hosts[0].roles['token auth']
        client = cli.Client(cls.cfg)
        client.run('openssl ecparam -genkey -name prime256v1 -noout -out {}'
                   .format(token_auth['private key']).split())
        client.run('openssl ec -in {} -pubout -out {}'.format(
            token_auth['private key'], token_auth['public key']).split())

        cls.client = api.Client(cls.cfg, api.page_handler)

        cls.repository = cls.client.post(CONTAINER_REPO_PATH, gen_repo())
        remote_data = gen_container_remote(upstream_name=DOCKERHUB_PULP_FIXTURE_1)
        cls.remote = cls.client.post(CONTAINER_REMOTE_PATH, remote_data)
        sync(cls.cfg, cls.remote, cls.repository)

        cls.distribution = cls.client.using_handler(api.task_handler).post(
            CONTAINER_DISTRIBUTION_PATH,
            gen_distribution(repository=cls.repository['pulp_href'])
        )

    @classmethod
    def tearDownClass(cls):
        """Clean generated resources."""
        cls.client.delete(cls.repository['pulp_href'])
        cls.client.delete(cls.remote['pulp_href'])
        cls.client.delete(cls.distribution['pulp_href'])

    def test_pull_image_with_raw_http_requests(self):
        """
        Test if a content was pulled from a registry by using raw HTTP requests.

        The registry offers a reference to a certified authority which generates a
        Bearer token. The generated Bearer token is afterwards used to pull the image.
        All requests are sent via aiohttp modules.
        """
        image_path = '/v2/{}/manifests/{}'.format(self.distribution['base_path'], 'manifest_a')
        latest_image_url = urljoin(self.cfg.get_content_host_base_url(), image_path)

        with self.assertRaises(HTTPError) as cm:
            self.client.get(latest_image_url, headers={'Accept': MEDIA_TYPE.MANIFEST_V2})

        content_response = cm.exception.response
        self.assertEqual(content_response.status_code, 401)

        authenticate_header = content_response.headers['Www-Authenticate']
        queries = AuthenticationHeaderQueries(authenticate_header)
        content_response = self.client.get(
            queries.realm,
            params={'service': queries.service, 'scope': queries.scope}
        )
        content_response = self.client.get(
            latest_image_url,
            auth=BearerTokenAuth(content_response['token']),
            headers={'Accept': MEDIA_TYPE.MANIFEST_V2}
        )
        self.compare_config_blob_digests(content_response['config']['digest'])

    def test_pull_image_with_real_docker_client(self):
        """
        Test if a CLI client is able to pull an image from an authenticated registry.

        This test checks if ordinary clients, like docker, or podman, are able to pull the
        image from a secured registry.
        """
        registry = cli.RegistryClient(self.cfg)
        registry.raise_if_unsupported(unittest.SkipTest, 'Test requires podman/docker')

        image_url = urljoin(
            self.cfg.get_content_host_base_url(),
            self.distribution['base_path']
        )
        image_with_tag = f'{image_url}:manifest_a'
        registry.pull(image_with_tag)

        image = registry.inspect(image_with_tag)
        self.compare_config_blob_digests(image[0]['Id'])

    def compare_config_blob_digests(self, pulled_manifest_digest):
        """Check if a valid config was pulled from a registry."""
        tags_by_name_url = f'{CONTAINER_TAG_PATH}?name=manifest_a'
        tag_response = self.client.get(tags_by_name_url)

        tagged_manifest_href = tag_response[0]['tagged_manifest']
        manifest_response = self.client.get(tagged_manifest_href)

        config_blob_response = self.client.get(manifest_response['config_blob'])
        self.assertEqual(pulled_manifest_digest, config_blob_response['digest'])


class AuthenticationHeaderQueries:
    """A data class to store header queries located in the Www-Authenticate header."""

    def __init__(self, authenticate_header):
        """Extract service, realm, and scope from the header."""
        realm, service, scope = authenticate_header[7:].split(',')
        # realm="rlm" -> rlm
        self.realm = realm[6:][1:-1]
        # service="srv" -> srv
        self.service = service[8:][1:-1]
        # scope="scp" -> scp
        self.scope = scope[6:][1:-1]


class BearerTokenAuth(AuthBase):
    """A subclass for building a JWT Authorization header out of a provided token."""

    def __init__(self, token):
        """Store a Bearer token that is going to be used in the request object."""
        self.token = token

    def __call__(self, r):
        """Attaches a Bearer token authentication to the given request object."""
        r.headers['Authorization'] = 'Bearer {}'.format(self.token)
        return r

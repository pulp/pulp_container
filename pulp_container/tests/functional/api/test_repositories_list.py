# coding=utf-8
"""Tests for fetching the list of all repositories."""
import unittest

from urllib.parse import urljoin
import requests
from requests.exceptions import HTTPError

from pulp_smash import api, config
from pulp_smash.pulp3.bindings import monitor_task
from pulp_smash.pulp3.utils import delete_orphans, gen_distribution, gen_repo

from pulp_container.tests.functional.constants import DOCKERHUB_PULP_FIXTURE_1

from pulp_container.tests.functional.utils import (
    del_user,
    gen_container_remote,
    gen_container_client,
    gen_user,
    BearerTokenAuth,
    AuthenticationHeaderQueries,
)

from pulpcore.client.pulp_container import (
    ContainerContainerRepository,
    ContainerContainerDistribution,
    ContainerContainerRemote,
    DistributionsContainerApi,
    PulpContainerNamespacesApi,
    RepositoriesContainerApi,
    RemotesContainerApi,
    RepositorySyncURL,
)


class RepositoriesList:
    """Base class used for initializing and listing repositories."""

    @classmethod
    def setUpClass(cls):
        """Create class wide-variables."""
        api_client = gen_container_client()
        cls.repositories_api = RepositoriesContainerApi(api_client)
        cls.remotes_api = RemotesContainerApi(api_client)
        cls.distributions_api = DistributionsContainerApi(api_client)
        cls.namespaces_api = PulpContainerNamespacesApi(api_client)

        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)

        cls.repository = cls.repositories_api.create(ContainerContainerRepository(**gen_repo()))

        remote_data = gen_container_remote(upstream_name=DOCKERHUB_PULP_FIXTURE_1)
        cls.remote = cls.remotes_api.create(ContainerContainerRemote(**remote_data))

        sync_data = RepositorySyncURL(remote=cls.remote.pulp_href)
        sync_response = cls.repositories_api.sync(cls.repository.pulp_href, sync_data)
        monitor_task(sync_response.task)

    def get_listed_repositories(self, auth=None):
        """Fetch repositories from the catalog endpoint."""
        repositories_list_endpoint = urljoin(self.cfg.get_base_url(), "/v2/_catalog")

        with self.assertRaises(HTTPError) as cm:
            requests.get(repositories_list_endpoint).raise_for_status()
        content_response = cm.exception.response
        authenticate_header = content_response.headers["Www-Authenticate"]

        queries = AuthenticationHeaderQueries(authenticate_header)
        self.assertEqual(queries.scope, "registry:catalog:*")

        content_response = requests.get(
            queries.realm, params={"service": queries.service, "scope": queries.scope}, auth=auth
        )
        content_response.raise_for_status()

        repositories = requests.get(
            repositories_list_endpoint, auth=BearerTokenAuth(content_response.json()["token"])
        )
        repositories.raise_for_status()
        return repositories


class RepositoriesListTestCase(RepositoriesList, unittest.TestCase):
    """Test case for listing all repositories within the registry."""

    @classmethod
    def setUpClass(cls):
        """Create class wide-variables."""
        super().setUpClass()

        distribution_data = gen_distribution(repository=cls.repository.pulp_href)
        distribution_response = cls.distributions_api.create(
            ContainerContainerDistribution(**distribution_data)
        )
        created_resources = monitor_task(distribution_response.task).created_resources
        cls.distribution1 = cls.distributions_api.read(created_resources[0])

        distribution_data = gen_distribution(repository=cls.repository.pulp_href)
        distribution_response = cls.distributions_api.create(
            ContainerContainerDistribution(**distribution_data)
        )
        created_resources = monitor_task(distribution_response.task).created_resources
        cls.distribution2 = cls.distributions_api.read(created_resources[0])

    @classmethod
    def tearDownClass(cls):
        """Clean generated resources."""
        cls.repositories_api.delete(cls.repository.pulp_href)
        cls.remotes_api.delete(cls.remote.pulp_href)

        cls.distributions_api.delete(cls.distribution1.pulp_href)
        cls.distributions_api.delete(cls.distribution2.pulp_href)

        delete_orphans()

    def test_listing_repositories(self):
        """Check if all repositories are correctly listed for an administrator."""
        repositories = self.get_listed_repositories()
        repositories_names = sorted([self.distribution1.base_path, self.distribution2.base_path])
        self.assertEqual(repositories.json(), {"repositories": repositories_names})


class RepositoriesListWithPermissionsTestCase(RepositoriesList, unittest.TestCase):
    """Test case for listing repositories within the registry with respect to users' permissions."""

    @classmethod
    def setUpClass(cls):
        """Create class wide-variables."""
        super().setUpClass()

        distribution_data = gen_distribution(repository=cls.repository.pulp_href, private=True)
        distribution_response = cls.distributions_api.create(
            ContainerContainerDistribution(**distribution_data)
        )
        created_resources = monitor_task(distribution_response.task).created_resources
        cls.distribution1 = cls.distributions_api.read(created_resources[0])
        cls.namespace1 = cls.namespaces_api.read(cls.distribution1.namespace)

        distribution_data = gen_distribution(repository=cls.repository.pulp_href, private=True)
        distribution_response = cls.distributions_api.create(
            ContainerContainerDistribution(**distribution_data)
        )
        created_resources = monitor_task(distribution_response.task).created_resources
        cls.distribution2 = cls.distributions_api.read(created_resources[0])

        distribution_data = gen_distribution(repository=cls.repository.pulp_href)
        distribution_response = cls.distributions_api.create(
            ContainerContainerDistribution(**distribution_data)
        )
        created_resources = monitor_task(distribution_response.task).created_resources
        cls.distribution3 = cls.distributions_api.read(created_resources[0])

        cls.user_none = gen_user()
        cls.user_all = gen_user(
            [
                "container.pull_containerdistribution",
                "container.namespace_pull_containerdistribution",
            ],
        )
        cls.user_only_dist1 = gen_user(
            object_permissions=[
                ("container.pull_containerdistribution", cls.distribution1.pulp_href),
                ("container.namespace_pull_containerdistribution", cls.namespace1.pulp_href),
            ]
        )

    @classmethod
    def tearDownClass(cls):
        """Clean generated resources."""
        cls.repositories_api.delete(cls.repository.pulp_href)
        cls.remotes_api.delete(cls.remote.pulp_href)

        cls.distributions_api.delete(cls.distribution1.pulp_href)
        cls.distributions_api.delete(cls.distribution2.pulp_href)
        cls.distributions_api.delete(cls.distribution3.pulp_href)

        del_user(cls.user_none)
        del_user(cls.user_all)
        del_user(cls.user_only_dist1)

        delete_orphans()

    def test_none_user(self):
        """Check if the user can see only public repositories."""
        auth = (self.user_none["username"], self.user_none["password"])
        repositories = self.get_listed_repositories(auth)
        self.assertEqual(repositories.json(), {"repositories": [self.distribution3.base_path]})

    def test_all_user(self):
        """Check if the user can see all repositories."""
        auth = (self.user_all["username"], self.user_all["password"])
        repositories = self.get_listed_repositories(auth)
        repositories_names = sorted(
            [
                self.distribution1.base_path,
                self.distribution2.base_path,
                self.distribution3.base_path,
            ]
        )
        self.assertEqual(repositories.json(), {"repositories": repositories_names})

    def test_only_dist1_user(self):
        """Check if the user can see all public repositories, but not all private repositories."""
        auth = (self.user_only_dist1["username"], self.user_only_dist1["password"])
        repositories = self.get_listed_repositories(auth)
        repositories_names = sorted([self.distribution1.base_path, self.distribution3.base_path])
        self.assertEqual(repositories.json(), {"repositories": repositories_names})

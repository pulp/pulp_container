"""Tests for fetching the list of all repositories."""

import pytest

from urllib.parse import urljoin
import requests

from pulp_container.tests.functional.constants import PULP_FIXTURE_1
from pulp_container.tests.functional.utils import (
    BearerTokenAuth,
    AuthenticationHeaderQueries,
)


@pytest.fixture
def synced_repo_and_remote(container_repo, container_remote_factory, container_sync):
    """Create class wide-variables."""
    remote = container_remote_factory(upstream_name=PULP_FIXTURE_1)
    container_sync(container_repo, remote)

    return container_repo, remote


@pytest.fixture
def get_listed_repositories(bindings_cfg, pulp_settings):
    """Fetch repositories from the catalog endpoint."""
    repositories_list_endpoint = urljoin(bindings_cfg.host, "/v2/_catalog")

    def _get_listed_repositories(auth=None):
        response = requests.get(repositories_list_endpoint)

        if pulp_settings.TOKEN_AUTH_DISABLED:
            return response

        with pytest.raises(requests.HTTPError):
            response.raise_for_status()

        authenticate_header = response.headers["Www-Authenticate"]

        queries = AuthenticationHeaderQueries(authenticate_header)
        assert queries.scopes == ["registry:catalog:*"]

        content_response = requests.get(
            queries.realm, params={"service": queries.service, "scope": queries.scopes}, auth=auth
        )
        content_response.raise_for_status()

        repositories = requests.get(
            repositories_list_endpoint, auth=BearerTokenAuth(content_response.json()["token"])
        )
        repositories.raise_for_status()
        return repositories

    return _get_listed_repositories


def test_listing_repositories(
    synced_repo_and_remote,
    container_distribution_factory,
    get_listed_repositories,
    full_path,
    bindings_cfg,
):
    """Check if all repositories are correctly listed for an administrator."""
    repository, remote = synced_repo_and_remote
    distribution1 = container_distribution_factory(repository=repository.pulp_href)
    distribution2 = container_distribution_factory(repository=repository.pulp_href)
    repositories = get_listed_repositories(auth=(bindings_cfg.username, bindings_cfg.password))
    repositories_names = sorted([full_path(distribution1), full_path(distribution2)])
    assert repositories.json() == {"repositories": repositories_names}


def test_list_repositories_with_permissions(
    get_listed_repositories,
    gen_user,
    synced_repo_and_remote,
    container_distribution_factory,
    container_bindings,
    full_path,
    pulp_settings,
):
    """Test case for listing repositories within the registry with respect to users' permissions."""
    repository, remote = synced_repo_and_remote
    distribution1 = container_distribution_factory(repository=repository.pulp_href, private=True)
    distribution2 = container_distribution_factory(repository=repository.pulp_href, private=True)
    distribution3 = container_distribution_factory(repository=repository.pulp_href)
    namespace1 = container_bindings.PulpContainerNamespacesApi.read(distribution1.namespace)
    user_none = gen_user()
    user_all = gen_user(
        model_roles=[
            "container.containerdistribution_consumer",
            "container.containernamespace_consumer",
        ]
    )
    user_only_dist1 = gen_user(
        object_roles=[
            ("container.containerdistribution_consumer", distribution1.pulp_href),
            ("container.containernamespace_consumer", namespace1.pulp_href),
        ]
    )
    repositories_names_sorted = sorted(
        [
            full_path(distribution1),
            full_path(distribution2),
            full_path(distribution3),
        ]
    )

    # Test none user: Check if the user can see only public repositories.
    auth = (user_none.username, user_none.password)
    repositories = get_listed_repositories(auth)
    if pulp_settings.TOKEN_AUTH_DISABLED:
        assert repositories.json() == {"repositories": repositories_names_sorted}
    else:
        assert repositories.json() == {"repositories": [full_path(distribution3)]}

    # Test all user: Check if the user can see all repositories.
    auth = (user_all.username, user_all.password)
    repositories = get_listed_repositories(auth)
    assert repositories.json() == {"repositories": repositories_names_sorted}

    # Test only dist1 user: Check if the user can see all public repositories,
    # but not all private repositories.
    auth = (user_only_dist1.username, user_only_dist1.password)
    repositories = get_listed_repositories(auth)

    if pulp_settings.TOKEN_AUTH_DISABLED:
        assert repositories.json() == {"repositories": repositories_names_sorted}
    else:
        repositories_names = sorted([full_path(distribution1), full_path(distribution3)])
        assert repositories.json() == {"repositories": repositories_names}

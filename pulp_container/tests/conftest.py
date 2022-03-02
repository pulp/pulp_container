import pytest

from pulpcore.client.pulp_container import ApiClient, RemotesContainerApi, RepositoriesContainerApi


@pytest.fixture(scope="session")
def container_client(bindings_cfg):
    """Fixture for container_client."""
    return ApiClient(bindings_cfg)


@pytest.fixture(scope="session")
def container_remote_api(container_client):
    """Container remote API fixture."""
    return RemotesContainerApi(container_client)


@pytest.fixture(scope="session")
def container_repository_api(container_client):
    """Container repository API fixture."""
    return RepositoriesContainerApi(container_client)

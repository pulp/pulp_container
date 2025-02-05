"""Tests that container sync repositories have RBAC."""

import pytest
import uuid


@pytest.mark.parallel
def test_rbac_sync_repositories(gen_user, container_bindings, pulp_settings, monitor_task):
    """RBAC sync repositories."""
    if pulp_settings.TOKEN_AUTH_DISABLED:
        pytest.skip("RBAC cannot be tested when token authentication is disabled")

    user1 = gen_user(model_roles=["container.containerrepository_creator"])
    user2 = gen_user(model_roles=["container.containerrepository_viewer"])
    user3 = gen_user()
    repository = None

    """Create a repository."""
    body = {"name": str(uuid.uuid4())}
    with user2, pytest.raises(container_bindings.ApiException):
        container_bindings.RepositoriesContainerApi.create(body)
    with user3, pytest.raises(container_bindings.ApiException):
        container_bindings.RepositoriesContainerApi.create(body)
    with user1:
        repository = container_bindings.RepositoriesContainerApi.create(body)

    """Read a repository by its href."""
    with user1:
        container_bindings.RepositoriesContainerApi.read(repository.pulp_href)
    with user2:
        # read with global read permission
        container_bindings.RepositoriesContainerApi.read(repository.pulp_href)
    with user3, pytest.raises(container_bindings.ApiException):
        # read without read permission
        container_bindings.RepositoriesContainerApi.read(repository.pulp_href)

    """Read a repository by its name."""
    with user1:
        page = container_bindings.RepositoriesContainerApi.list(name=repository.name)
        assert len(page.results) == 1
    with user2:
        page = container_bindings.RepositoriesContainerApi.list(name=repository.name)
        assert len(page.results) == 1
    with user3:
        page = container_bindings.RepositoriesContainerApi.list(name=repository.name)
        assert len(page.results) == 0

    """Update a repository using HTTP PATCH."""
    body = {"name": str(uuid.uuid4())}
    with user2, pytest.raises(container_bindings.ApiException):
        container_bindings.RepositoriesContainerApi.partial_update(repository.pulp_href, body)
    with user3, pytest.raises(container_bindings.ApiException):
        container_bindings.RepositoriesContainerApi.partial_update(repository.pulp_href, body)
    with user1:
        response = container_bindings.RepositoriesContainerApi.partial_update(
            repository.pulp_href, body
        )
        monitor_task(response.task)
        repository = container_bindings.RepositoriesContainerApi.read(repository.pulp_href)

    """Update a repository using HTTP PUT."""
    body = {"name": str(uuid.uuid4())}
    with user2, pytest.raises(container_bindings.ApiException):
        container_bindings.RepositoriesContainerApi.update(repository.pulp_href, body)
    with user3, pytest.raises(container_bindings.ApiException):
        container_bindings.RepositoriesContainerApi.update(repository.pulp_href, body)
    with user1:
        response = container_bindings.RepositoriesContainerApi.update(repository.pulp_href, body)
        monitor_task(response.task)
        repository = container_bindings.RepositoriesContainerApi.read(repository.pulp_href)

    """Delete a repository."""
    with user2, pytest.raises(container_bindings.ApiException):
        container_bindings.RepositoriesContainerApi.delete(repository.pulp_href)
    with user3, pytest.raises(container_bindings.ApiException):
        container_bindings.RepositoriesContainerApi.delete(repository.pulp_href)
    with user1:
        response = container_bindings.RepositoriesContainerApi.delete(repository.pulp_href)
        monitor_task(response.task)
        with pytest.raises(container_bindings.ApiException):
            container_bindings.RepositoriesContainerApi.read(repository.pulp_href)

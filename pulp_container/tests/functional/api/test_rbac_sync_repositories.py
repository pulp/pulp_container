# coding=utf-8
"""Tests that container sync repositories have RBAC."""
import pytest

from pulp_smash import utils
from pulp_smash.pulp3.bindings import monitor_task

from pulpcore.client.pulp_container.exceptions import ApiException


@pytest.mark.parallel
def test_rbac_sync_repositories(gen_user, container_repository_api):
    """RBAC sync repositories."""

    user1 = gen_user(model_roles=["container.containerrepository_creator"])
    user2 = gen_user(model_roles=["container.containerrepository_viewer"])
    user3 = gen_user()
    repository = None

    """Create a repository."""
    body = {"name": utils.uuid4()}
    with user2, pytest.raises(ApiException):
        container_repository_api.create(body)
    with user3, pytest.raises(ApiException):
        container_repository_api.create(body)
    with user1:
        repository = container_repository_api.create(body)

    """Read a repository by its href."""
    with user1:
        container_repository_api.read(repository.pulp_href)
    with user2:
        # read with global read permission
        container_repository_api.read(repository.pulp_href)
    with user3, pytest.raises(ApiException):
        # read without read permission
        container_repository_api.read(repository.pulp_href)

    """Read a repository by its name."""
    with user1:
        page = container_repository_api.list(name=repository.name)
        assert len(page.results) == 1
    with user2:
        page = container_repository_api.list(name=repository.name)
        assert len(page.results) == 1
    with user3:
        page = container_repository_api.list(name=repository.name)
        assert len(page.results) == 0

    """Update a repository using HTTP PATCH."""
    body = {"name": utils.uuid4()}
    with user2, pytest.raises(ApiException):
        container_repository_api.partial_update(repository.pulp_href, body)
    with user3, pytest.raises(ApiException):
        container_repository_api.partial_update(repository.pulp_href, body)
    with user1:
        response = container_repository_api.partial_update(repository.pulp_href, body)
        monitor_task(response.task)
        repository = container_repository_api.read(repository.pulp_href)

    """Update a repository using HTTP PUT."""
    body = {"name": utils.uuid4()}
    with user2, pytest.raises(ApiException):
        container_repository_api.update(repository.pulp_href, body)
    with user3, pytest.raises(ApiException):
        container_repository_api.update(repository.pulp_href, body)
    with user1:
        response = container_repository_api.update(repository.pulp_href, body)
        monitor_task(response.task)
        repository = container_repository_api.read(repository.pulp_href)

    """Delete a repository."""
    with user2, pytest.raises(ApiException):
        container_repository_api.delete(repository.pulp_href)
    with user3, pytest.raises(ApiException):
        container_repository_api.delete(repository.pulp_href)
    with user1:
        response = container_repository_api.delete(repository.pulp_href)
        monitor_task(response.task)
        with pytest.raises(ApiException):
            container_repository_api.read(repository.pulp_href)

"""Tests that verify that RBAC for push repository works properly."""

import pytest

from django.conf import settings

from pulp_smash import utils
from pulp_smash.pulp3.bindings import monitor_task

from pulpcore.client.pulp_container.exceptions import ApiException

from pulp_container.tests.functional.constants import REGISTRY_V2_REPO_PULP


def test_rbac_push_repository(
    add_to_cleanup,
    gen_user,
    registry_client,
    local_registry,
    container_namespace_api,
    container_push_repository_api,
):
    """Verify RBAC for a ContainerPushRepository."""
    if settings.TOKEN_AUTH_DISABLED:
        pytest.skip("RBAC cannot be tested when token authentication is disabled")

    namespace_name = utils.uuid4()
    repo_name = f"{namespace_name}/perms"
    local_url = f"{repo_name}:1.0"

    user_creator = gen_user(
        model_roles=[
            "container.containerdistribution_creator",
            "container.containernamespace_creator",
        ]
    )
    user_reader = gen_user(model_roles=["container.containerdistribution_consumer"])
    user_helpless = gen_user()

    # create a push repo
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_d"
    registry_client.pull(image_path)
    with user_creator:
        local_registry.tag_and_push(image_path, local_url)
        repository = container_push_repository_api.list(name=repo_name).results[0]

    # Remove namespace after test
    namespace = container_namespace_api.list(name=namespace_name).results[0]
    add_to_cleanup(container_namespace_api, namespace.pulp_href)

    """Read a repository by its href."""
    with user_creator:
        container_push_repository_api.read(repository.pulp_href)
    # read with global read permission
    with user_reader:
        container_push_repository_api.read(repository.pulp_href)
    # read without read permission
    with user_helpless, pytest.raises(ApiException):
        container_push_repository_api.read(repository.pulp_href)

    """Read a repository by its name."""
    with user_creator:
        page = container_push_repository_api.list(name=repository.name)
        assert len(page.results) == 1
    with user_reader:
        page = container_push_repository_api.list(name=repository.name)
        assert len(page.results) == 1
    # this is a public repo
    with user_helpless:
        page = container_push_repository_api.list(name=repository.name)
        assert len(page.results) == 1

    """Update a repository using HTTP PATCH."""
    body = {"description": "new_hotness"}
    with user_helpless, pytest.raises(ApiException):
        container_push_repository_api.partial_update(repository.pulp_href, body)
    with user_reader, pytest.raises(ApiException):
        container_push_repository_api.partial_update(repository.pulp_href, body)
    with user_creator:
        response = container_push_repository_api.partial_update(repository.pulp_href, body)
        monitor_task(response.task)
        repository = container_push_repository_api.read(repository.pulp_href)
        assert repository.description == body["description"]

    """Update a repository using HTTP PUT."""
    body = {"name": repository.name, "description": "old_busted"}
    with user_helpless, pytest.raises(ApiException):
        container_push_repository_api.update(repository.pulp_href, body)
    with user_reader, pytest.raises(ApiException):
        container_push_repository_api.update(repository.pulp_href, body)
    with user_creator:
        response = container_push_repository_api.update(repository.pulp_href, body)
        monitor_task(response.task)
    with user_creator:
        repository = container_push_repository_api.read(repository.pulp_href)
        assert repository.description == body["description"]

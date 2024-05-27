"""Tests that verify that RBAC for content works properly."""

import pytest

from django.conf import settings

from pulp_smash.pulp3.bindings import monitor_task
from pulp_smash.pulp3.utils import gen_repo

from pulpcore.client.pulp_container.exceptions import ApiException

from pulp_container.tests.functional.constants import PULP_FIXTURE_1, REGISTRY_V2_REPO_PULP
from pulp_container.tests.functional.utils import (
    gen_container_remote,
)

from pulpcore.client.pulp_container import (
    ContainerContainerRepository,
    ContainerRepositorySyncURL,
)


def test_rbac_repository_content(
    delete_orphans_pre,
    add_to_cleanup,
    gen_object_with_cleanup,
    gen_user,
    registry_client,
    local_registry,
    container_remote_api,
    container_repository_api,
    container_push_repository_api,
    container_distribution_api,
    container_namespace_api,
    container_tag_api,
):
    """Assert that certain users can list and read content."""
    if settings.TOKEN_AUTH_DISABLED:
        pytest.skip("RBAC cannot be tested when token authentication is disabled")

    user_creator = gen_user(
        model_roles=[
            "container.containernamespace_creator",
            "container.containerremote_creator",
            "container.containerrepository_creator",
        ],
    )
    user_creator2 = gen_user(
        model_roles=[
            "container.containernamespace_creator",
            "container.containerremote_creator",
        ]
    )
    user_reader = gen_user(
        model_roles=[
            "container.containerrepository_viewer",
            "container.containerdistribution_consumer",
        ]
    )
    user_reader2 = gen_user(model_roles=["container.containerrepository_viewer"])
    user_reader3 = gen_user(model_roles=["container.containerdistribution_consumer"])
    user_helpless = gen_user()

    # create a first push repo with user_creator
    image_path1 = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    registry_client.pull(image_path1)
    repo_name1 = "testcontent1/perms"
    local_url1 = f"{repo_name1}:1.0"
    with user_creator:
        local_registry.tag_and_push(image_path1, local_url1)
        push_repository1 = container_push_repository_api.list(name=repo_name1).results[0]
    distribution1 = container_distribution_api.list(name=repo_name1).results[0]
    add_to_cleanup(container_namespace_api, distribution1.namespace)

    # create a second push repo with user_creator2
    image_path2 = f"{REGISTRY_V2_REPO_PULP}:manifest_b"
    registry_client.pull(image_path2)
    repo_name2 = "testcontent2/perms"
    local_url2 = f"{repo_name2}:1.0"
    with user_creator2:
        local_registry.tag_and_push(image_path2, local_url2)
        push_repository2 = container_push_repository_api.list(name=repo_name2).results[0]
    distribution2 = container_distribution_api.list(name=repo_name2).results[0]
    add_to_cleanup(container_namespace_api, distribution2.namespace)

    # sync a repo with user_creator
    with user_creator:
        remote = gen_object_with_cleanup(
            container_remote_api, gen_container_remote(upstream_name=PULP_FIXTURE_1)
        )
        repository = gen_object_with_cleanup(
            container_repository_api,
            ContainerContainerRepository(**gen_repo()),
        )
        sync_data = ContainerRepositorySyncURL(remote=remote.pulp_href)
        sync_response = container_repository_api.sync(repository.pulp_href, sync_data)
        monitor_task(sync_response.task)

    # Test that users can list content if they have enough permissions.
    push_repository1_rv = container_push_repository_api.read(
        push_repository1.pulp_href
    ).latest_version_href
    push_repository2_rv = container_push_repository_api.read(
        push_repository2.pulp_href
    ).latest_version_href
    repository_rv = container_repository_api.read(repository.pulp_href).latest_version_href

    with user_creator:
        assert container_tag_api.list().count == 10
        assert container_tag_api.list(repository_version=push_repository1_rv).count == 1
        assert container_tag_api.list(repository_version=push_repository2_rv).count == 0
        assert container_tag_api.list(repository_version=repository_rv).count == 9

    with user_creator2:
        assert container_tag_api.list().count == 1
        assert container_tag_api.list(repository_version=push_repository1_rv).count == 0
        assert container_tag_api.list(repository_version=push_repository2_rv).count == 1
        assert container_tag_api.list(repository_version=repository_rv).count == 0

    with user_reader:
        assert container_tag_api.list().count == 11
        assert container_tag_api.list(repository_version=push_repository1_rv).count == 1
        assert container_tag_api.list(repository_version=push_repository2_rv).count == 1
        assert container_tag_api.list(repository_version=repository_rv).count == 9

    with user_reader2:
        assert container_tag_api.list().count == 9
        assert container_tag_api.list(repository_version=push_repository1_rv).count == 0
        assert container_tag_api.list(repository_version=push_repository2_rv).count == 0
        assert container_tag_api.list(repository_version=repository_rv).count == 9

    with user_reader3:
        assert container_tag_api.list().count == 2
        assert container_tag_api.list(repository_version=push_repository1_rv).count == 1
        assert container_tag_api.list(repository_version=push_repository2_rv).count == 1
        assert container_tag_api.list(repository_version=repository_rv).count == 0

    with user_helpless:
        assert container_tag_api.list().count == 0
        assert container_tag_api.list(repository_version=push_repository1_rv).count == 0
        assert container_tag_api.list(repository_version=push_repository2_rv).count == 0
        assert container_tag_api.list(repository_version=repository_rv).count == 0

    # Test that users can read specific content if they have enough permissions.

    pushed_tag = container_tag_api.list(
        repository_version_added=push_repository1.latest_version_href
    ).results[0]
    container_tag_api.read(pushed_tag.pulp_href)
    with user_creator:
        container_tag_api.read(pushed_tag.pulp_href)
    with user_creator2, pytest.raises(ApiException):
        container_tag_api.read(pushed_tag.pulp_href)
    with user_reader:
        container_tag_api.read(pushed_tag.pulp_href)
    with user_reader2, pytest.raises(ApiException):
        container_tag_api.read(pushed_tag.pulp_href)
    with user_reader3:
        container_tag_api.read(pushed_tag.pulp_href)
    with user_helpless, pytest.raises(ApiException):
        container_tag_api.read(pushed_tag.pulp_href)

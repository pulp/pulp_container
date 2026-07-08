"""Tests for migrating push repositories to container repositories."""

import uuid

from pulp_container.tests.functional.constants import REGISTRY_V2_REPO_PULP


def test_migrate_push_repository(
    add_to_cleanup,
    container_push_repository_factory,
    registry_client,
    local_registry,
    container_bindings,
    full_path,
    monitor_task,
):
    """A push repository can be migrated to a container repository."""
    namespace_name = str(uuid.uuid4())
    repo_name = f"{namespace_name}/migrate"
    local_url = full_path(f"{repo_name}:1.0")

    container_push_repository_factory(name=repo_name)
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    registry_client.pull(image_path)
    local_registry.tag_and_push(image_path, local_url)

    distribution = container_bindings.DistributionsContainerApi.list(name=repo_name).results[0]
    namespace = container_bindings.PulpContainerNamespacesApi.read(distribution.namespace)
    add_to_cleanup(container_bindings.PulpContainerNamespacesApi, namespace.pulp_href)

    push_repository = container_bindings.RepositoriesContainerPushApi.list(name=repo_name).results[
        0
    ]
    tags_before = container_bindings.ContentTagsApi.list(
        repository_version=push_repository.latest_version_href
    )
    assert tags_before.count == 1

    migrate_response = container_bindings.RepositoriesContainerPushApi.migrate(
        push_repository.pulp_href, {"copy_versions": False}
    )
    task = monitor_task(migrate_response.task)
    container_repository = container_bindings.RepositoriesContainerApi.read(
        task.result["pulp_href"]
    )
    assert container_repository.name == repo_name
    assert container_repository.pulp_href in task.created_resources
    assert container_repository.prn == task.result["prn"]
    tags_after = container_bindings.ContentTagsApi.list(
        repository_version=container_repository.latest_version_href
    )
    assert tags_after.count == 1
    assert tags_after.results[0].name == tags_before.results[0].name
    assert tags_after.results[0].prn == tags_before.results[0].prn

    assert container_bindings.RepositoriesContainerPushApi.list(name=repo_name).count == 0

    distribution = container_bindings.DistributionsContainerApi.list(name=repo_name).results[0]
    assert distribution.repository == container_repository.pulp_href

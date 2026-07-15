"""Tests for migrating push repositories to container repositories."""

import uuid

from pulp_container.tests.functional.constants import REGISTRY_V2_REPO_PULP


def _setup_push_repository(
    add_to_cleanup,
    container_push_repository_factory,
    registry_client,
    local_registry,
    container_bindings,
    full_path,
    repo_name,
    tag="1.0",
):
    """Create a legacy push repository, push an image, and register cleanup."""
    local_url = full_path(f"{repo_name}:{tag}")

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
    return push_repository, local_url


def test_migrate_push_repository(
    add_to_cleanup,
    container_push_repository_factory,
    registry_client,
    local_registry,
    container_bindings,
    full_path,
    monitor_task,
):
    """A push repository can be migrated to a container repository and still accept pushes."""
    namespace_name = str(uuid.uuid4())
    repo_name = f"{namespace_name}/migrate"

    push_repository, local_url = _setup_push_repository(
        add_to_cleanup,
        container_push_repository_factory,
        registry_client,
        local_registry,
        container_bindings,
        full_path,
        repo_name,
    )
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

    image_path_b = f"{REGISTRY_V2_REPO_PULP}:manifest_b"
    registry_client.pull(image_path_b)
    local_registry.tag_and_push(image_path_b, full_path(f"{repo_name}:2.0"))

    container_repository = container_bindings.RepositoriesContainerApi.read(
        container_repository.pulp_href
    )
    tags_after_push = container_bindings.ContentTagsApi.list(
        repository_version=container_repository.latest_version_href
    )
    assert tags_after_push.count == 2
    assert {tag.name for tag in tags_after_push.results} == {"1.0", "2.0"}
    local_registry.pull(local_url)


def test_migrate_push_repository_copy_versions(
    add_to_cleanup,
    container_push_repository_factory,
    registry_client,
    local_registry,
    container_bindings,
    full_path,
    monitor_task,
):
    """Migrating with copy_versions=True preserves repository version history content."""
    namespace_name = str(uuid.uuid4())
    repo_name = f"{namespace_name}/migrate-versions"

    push_repository, _ = _setup_push_repository(
        add_to_cleanup,
        container_push_repository_factory,
        registry_client,
        local_registry,
        container_bindings,
        full_path,
        repo_name,
        tag="1.0",
    )

    image_path_b = f"{REGISTRY_V2_REPO_PULP}:manifest_b"
    registry_client.pull(image_path_b)
    local_registry.tag_and_push(image_path_b, full_path(f"{repo_name}:2.0"))

    push_repository = container_bindings.RepositoriesContainerPushApi.read(
        push_repository.pulp_href
    )
    push_versions = container_bindings.RepositoriesContainerPushVersionsApi.list(
        push_repository.pulp_href
    )
    # version 0 (empty) plus one version per push
    assert push_versions.count >= 3

    version_tag_counts = []
    for version in sorted(push_versions.results, key=lambda v: v.number):
        if version.number == 0:
            continue
        tags = container_bindings.ContentTagsApi.list(repository_version=version.pulp_href)
        version_tag_counts.append((version.number, tags.count, {t.name for t in tags.results}))

    migrate_response = container_bindings.RepositoriesContainerPushApi.migrate(
        push_repository.pulp_href, {"copy_versions": True}
    )
    task = monitor_task(migrate_response.task)
    container_repository = container_bindings.RepositoriesContainerApi.read(
        task.result["pulp_href"]
    )

    container_versions = container_bindings.RepositoriesContainerVersionsApi.list(
        container_repository.pulp_href
    )
    migrated_versions = sorted(
        [v for v in container_versions.results if v.number != 0],
        key=lambda v: v.number,
    )
    assert len(migrated_versions) == len(version_tag_counts)

    for (_, expected_count, expected_names), migrated in zip(version_tag_counts, migrated_versions):
        tags = container_bindings.ContentTagsApi.list(repository_version=migrated.pulp_href)
        assert tags.count == expected_count
        assert {t.name for t in tags.results} == expected_names

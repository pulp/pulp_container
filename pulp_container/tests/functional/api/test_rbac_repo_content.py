"""Tests that verify that RBAC for content works properly."""

import pytest


from pulp_container.tests.functional.constants import PULP_FIXTURE_1, REGISTRY_V2_REPO_PULP


def test_rbac_repository_content(
    delete_orphans_pre,
    add_to_cleanup,
    gen_user,
    registry_client,
    local_registry,
    container_bindings,
    container_remote_factory,
    container_repository_factory,
    full_path,
    pulp_settings,
    monitor_task,
):
    """Assert that certain users can list and read content."""
    if pulp_settings.TOKEN_AUTH_DISABLED:
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
    local_url1 = full_path(f"{repo_name1}:1.0")
    with user_creator:
        local_registry.tag_and_push(image_path1, local_url1)
        push_repository1 = container_bindings.RepositoriesContainerPushApi.list(
            name=repo_name1
        ).results[0]
    distribution1 = container_bindings.DistributionsContainerApi.list(name=repo_name1).results[0]
    add_to_cleanup(container_bindings.PulpContainerNamespacesApi, distribution1.namespace)

    # create a second push repo with user_creator2
    image_path2 = f"{REGISTRY_V2_REPO_PULP}:manifest_b"
    registry_client.pull(image_path2)
    repo_name2 = "testcontent2/perms"
    local_url2 = full_path(f"{repo_name2}:1.0")
    with user_creator2:
        local_registry.tag_and_push(image_path2, local_url2)
        push_repository2 = container_bindings.RepositoriesContainerPushApi.list(
            name=repo_name2
        ).results[0]
    distribution2 = container_bindings.DistributionsContainerApi.list(name=repo_name2).results[0]
    add_to_cleanup(container_bindings.PulpContainerNamespacesApi, distribution2.namespace)

    # sync a repo with user_creator
    with user_creator:
        remote = container_remote_factory(upstream_name=PULP_FIXTURE_1)
        repository = container_repository_factory()
        sync_data = {"remote": remote.pulp_href}
        sync_response = container_bindings.RepositoriesContainerApi.sync(
            repository.pulp_href, sync_data
        )
        monitor_task(sync_response.task)

    # Test that users can list content if they have enough permissions.
    push_repository1_rv = container_bindings.RepositoriesContainerPushApi.read(
        push_repository1.pulp_href
    ).latest_version_href
    push_repository2_rv = container_bindings.RepositoriesContainerPushApi.read(
        push_repository2.pulp_href
    ).latest_version_href
    repository_rv = container_bindings.RepositoriesContainerApi.read(
        repository.pulp_href
    ).latest_version_href

    with user_creator:
        assert container_bindings.ContentTagsApi.list().count == 10
        assert (
            container_bindings.ContentTagsApi.list(repository_version=push_repository1_rv).count
            == 1
        )
        assert (
            container_bindings.ContentTagsApi.list(repository_version=push_repository2_rv).count
            == 0
        )
        assert container_bindings.ContentTagsApi.list(repository_version=repository_rv).count == 9

    with user_creator2:
        assert container_bindings.ContentTagsApi.list().count == 1
        assert (
            container_bindings.ContentTagsApi.list(repository_version=push_repository1_rv).count
            == 0
        )
        assert (
            container_bindings.ContentTagsApi.list(repository_version=push_repository2_rv).count
            == 1
        )
        assert container_bindings.ContentTagsApi.list(repository_version=repository_rv).count == 0

    with user_reader:
        assert container_bindings.ContentTagsApi.list().count == 11
        assert (
            container_bindings.ContentTagsApi.list(repository_version=push_repository1_rv).count
            == 1
        )
        assert (
            container_bindings.ContentTagsApi.list(repository_version=push_repository2_rv).count
            == 1
        )
        assert container_bindings.ContentTagsApi.list(repository_version=repository_rv).count == 9

    with user_reader2:
        assert container_bindings.ContentTagsApi.list().count == 9
        assert (
            container_bindings.ContentTagsApi.list(repository_version=push_repository1_rv).count
            == 0
        )
        assert (
            container_bindings.ContentTagsApi.list(repository_version=push_repository2_rv).count
            == 0
        )
        assert container_bindings.ContentTagsApi.list(repository_version=repository_rv).count == 9

    with user_reader3:
        assert container_bindings.ContentTagsApi.list().count == 2
        assert (
            container_bindings.ContentTagsApi.list(repository_version=push_repository1_rv).count
            == 1
        )
        assert (
            container_bindings.ContentTagsApi.list(repository_version=push_repository2_rv).count
            == 1
        )
        assert container_bindings.ContentTagsApi.list(repository_version=repository_rv).count == 0

    with user_helpless:
        assert container_bindings.ContentTagsApi.list().count == 0
        assert (
            container_bindings.ContentTagsApi.list(repository_version=push_repository1_rv).count
            == 0
        )
        assert (
            container_bindings.ContentTagsApi.list(repository_version=push_repository2_rv).count
            == 0
        )
        assert container_bindings.ContentTagsApi.list(repository_version=repository_rv).count == 0

    # Test that users can read specific content if they have enough permissions.

    pushed_tag = container_bindings.ContentTagsApi.list(
        repository_version_added=push_repository1.latest_version_href
    ).results[0]
    container_bindings.ContentTagsApi.read(pushed_tag.pulp_href)
    with user_creator:
        container_bindings.ContentTagsApi.read(pushed_tag.pulp_href)
    with user_creator2, pytest.raises(container_bindings.ApiException):
        container_bindings.ContentTagsApi.read(pushed_tag.pulp_href)
    with user_reader:
        container_bindings.ContentTagsApi.read(pushed_tag.pulp_href)
    with user_reader2, pytest.raises(container_bindings.ApiException):
        container_bindings.ContentTagsApi.read(pushed_tag.pulp_href)
    with user_reader3:
        container_bindings.ContentTagsApi.read(pushed_tag.pulp_href)
    with user_helpless, pytest.raises(container_bindings.ApiException):
        container_bindings.ContentTagsApi.read(pushed_tag.pulp_href)

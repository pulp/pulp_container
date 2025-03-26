"""Tests that verify that RBAC for content works properly."""

import pytest


from pulp_container.tests.functional.constants import PULP_FIXTURE_1, REGISTRY_V2_REPO_PULP
from pulpcore.client.pulp_container.exceptions import ForbiddenException
from pulpcore.client.pulp_container import SetLabel, UnsetLabel


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


def test_rbac_label_content(
    gen_user,
    container_bindings,
    container_remote_factory,
    container_repository_factory,
    container_repository_version_api,
    container_sync,
    pulp_settings,
):

    def _do_test(the_binding, the_content, rv):
        # Set label
        sl = SetLabel(key="key_1", value="value_1")
        the_binding.set_label(the_content.pulp_href, sl)
        the_content = the_binding.read(the_content.pulp_href)
        labels = the_content.pulp_labels
        assert "key_1" in labels

        # Search for key_1
        rslt = the_binding.list(pulp_label_select="key_1", repository_version=rv.pulp_href)
        assert 1 == rslt.count

        # Change an existing label
        sl = SetLabel(key="key_1", value="XXX")
        the_binding.set_label(the_content.pulp_href, sl)
        the_content = the_binding.read(the_content.pulp_href)
        labels = the_content.pulp_labels
        assert labels["key_1"] == "XXX"

        # Unset a label
        sl = UnsetLabel(key="key_1")
        the_binding.unset_label(the_content.pulp_href, sl)
        content2 = the_binding.read(the_content.pulp_href)
        assert "key_1" not in content2.pulp_labels

    content_units = []
    repo_owner = gen_user(
        model_roles=[
            "container.containernamespace_creator",
            "container.containerremote_creator",
            "container.containerrepository_creator",
            "core.content_labeler",
        ]
    )
    # Set up and sync a repository with the desired the_content-types
    # Show that the_content-labeler can set/unset_label
    with repo_owner:
        repo = container_repository_factory()
        remote = container_remote_factory()
        version_href = container_sync(repo, remote).created_resources[0]
        repo_version = container_repository_version_api.read(version_href)

        # Test set/unset/search for each type-of-the_content
        # We don't do this via pytest-parameterization so that we only sync the repo *once*.
        content_bindings = [
            container_bindings.ContentBlobsApi,
            container_bindings.ContentManifestsApi,
            container_bindings.ContentTagsApi,
        ]
        for a_binding in content_bindings:
            # Pick first the_content-unit from list of those "present" for specified type
            # in specified repository-version
            a_content = a_binding.list(repository_version=repo_version.pulp_href).results[0]
            content_units.append((a_binding, a_content))
            _do_test(a_binding, a_content, repo_version)

    # Show that a repository-viewer DOES NOT HAVE access to set/unset_label
    viewer = gen_user(model_roles=["container.containerrepository_viewer"])
    with viewer:
        for binding, content in content_units:
            with pytest.raises(ForbiddenException):
                label = SetLabel(key="key_1", value="XXX")
                binding.set_label(content.pulp_href, label)

            with pytest.raises(ForbiddenException):
                label = UnsetLabel(key="key_1")
                binding.unset_label(content.pulp_href, label)

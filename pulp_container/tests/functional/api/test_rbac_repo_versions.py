"""Tests that verify that RBAC for repository versions work properly."""

import pytest

from django.conf import settings

from pulp_smash import utils
from pulp_smash.pulp3.bindings import monitor_task
from pulp_smash.pulp3.utils import gen_repo

from pulpcore.client.pulp_container.exceptions import ApiException

from pulp_container.tests.functional.constants import PULP_FIXTURE_1, REGISTRY_V2_REPO_PULP
from pulp_container.tests.functional.utils import TOKEN_AUTH_DISABLED, gen_container_remote

from pulpcore.client.pulp_container import (
    ContainerContainerRepository,
    ContainerRepositorySyncURL,
    TagImage,
)


def test_rbac_repository_version(
    gen_user,
    gen_object_with_cleanup,
    container_repository_api,
    container_repository_version_api,
    container_remote_api,
    container_tag_api,
    container_manifest_api,
):
    """Verify RBAC for a ContainerRepositoryVersion."""
    if settings.TOKEN_AUTH_DISABLED:
        pytest.skip("RBAC cannot be tested when token authentication is disabled")

    user_creator = gen_user(
        model_roles=[
            "container.containerrepository_creator",
            "container.containerremote_creator",
        ]
    )
    user_repo_content_manager = gen_user(
        model_roles=[
            "container.containerrepository_content_manager",
        ]
    )
    user_repo_owner = gen_user(
        model_roles=[
            "container.containerrepository_owner",
        ]
    )
    user_reader = gen_user(model_roles=["container.containerrepository_viewer"])
    user_helpless = gen_user()

    # sync a repo
    with user_creator:
        repository = gen_object_with_cleanup(
            container_repository_api, ContainerContainerRepository(**gen_repo())
        )
        remote = gen_object_with_cleanup(
            container_remote_api, gen_container_remote(upstream_name=PULP_FIXTURE_1)
        )
        sync_data = ContainerRepositorySyncURL(remote=remote.pulp_href)
        sync_response = container_repository_api.sync(repository.pulp_href, sync_data)
        monitor_task(sync_response.task)
        repository = container_repository_api.read(repository.pulp_href)

    """
    Test that users can list repository versions if they have enough rights
    """
    assert container_repository_version_api.list(repository.pulp_href).count == 2
    with user_creator:
        assert container_repository_version_api.list(repository.pulp_href).count == 2
    with user_reader:
        assert container_repository_version_api.list(repository.pulp_href).count == 2
    with user_helpless, pytest.raises(ApiException):
        container_repository_version_api.list(repository.pulp_href)

    """
    Test that users can read specific repository versions if they have enough rights
    """
    container_repository_version_api.read(repository.latest_version_href)
    with user_creator:
        container_repository_version_api.read(repository.latest_version_href)
    with user_reader:
        container_repository_version_api.read(repository.latest_version_href)
    with user_helpless, pytest.raises(ApiException):
        container_repository_version_api.read(repository.latest_version_href)

    """
    Test that users can delete repository versions if they have enough rights
    """

    manifest_a = container_manifest_api.read(
        container_tag_api.list(name="manifest_a", repository_version=repository.latest_version_href)
        .results[0]
        .tagged_manifest
    )

    def create_new_repo_version():
        """
        Create a new repo version to delete it later by a test user
        """
        nonlocal repository

        tag_data = TagImage(tag="new_tag", digest=manifest_a.digest)
        tag_response = container_repository_api.tag(repository.pulp_href, tag_data)
        monitor_task(tag_response.task)
        repository = container_repository_api.read(repository.pulp_href)
        return repository.latest_version_href

    with user_helpless, pytest.raises(ApiException):
        container_repository_api.delete(repository.latest_version_href)
    with user_reader, pytest.raises(ApiException):
        container_repository_api.delete(repository.latest_version_href)

    response = container_repository_version_api.delete(create_new_repo_version())
    monitor_task(response.task)

    with user_creator:
        response = container_repository_version_api.delete(create_new_repo_version())
        monitor_task(response.task)

    with user_repo_content_manager:
        response = container_repository_version_api.delete(create_new_repo_version())
        monitor_task(response.task)

    with user_repo_owner:
        response = container_repository_version_api.delete(create_new_repo_version())
        monitor_task(response.task)


def test_rbac_push_repository_version(
    add_to_cleanup,
    gen_user,
    registry_client,
    local_registry,
    container_namespace_api,
    container_push_repository_api,
    container_push_repository_version_api,
):
    """Verify RBAC for a ContainerPushRepositoryVersion."""
    if settings.TOKEN_AUTH_DISABLED:
        pytest.skip("RBAC cannot be tested when token authentication is disabled")

    try:
        # Remove namespace to start out clean
        namespace = container_namespace_api.list(name="test_push_repo").results[0]
        container_namespace_api.delete(namespace.pulp_href)
    except IndexError:
        pass

    user_creator = gen_user(
        model_roles=[
            "container.containernamespace_creator",
        ]
    )
    user_reader = gen_user(model_roles=["container.containerdistribution_consumer"])
    user_helpless = gen_user()

    # create a push repo
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_d"
    registry_client.pull(image_path)
    repo_name = "test_push_repo/perms"
    local_url = f"{repo_name}:1.0"
    with user_creator:
        local_registry.tag_and_push(image_path, local_url)
        repository = container_push_repository_api.list(name=repo_name).results[0]

    # Remove namespace after the test
    add_to_cleanup(
        container_namespace_api,
        container_namespace_api.list(name="test_push_repo").results[0].pulp_href,
    )

    """
    Test that users can list repository versions if they have enough permissions
    """
    assert container_push_repository_version_api.list(repository.pulp_href).count == 2
    with user_creator:
        assert container_push_repository_version_api.list(repository.pulp_href).count == 2
    with user_reader:
        assert container_push_repository_version_api.list(repository.pulp_href).count == 2
    with user_helpless, pytest.raises(ApiException):
        container_push_repository_version_api.list(repository.pulp_href)

    """
    Test that users can read specific repository versions if they have enough permissions
    """
    container_push_repository_version_api.read(repository.latest_version_href)
    with user_creator:
        container_push_repository_version_api.read(repository.latest_version_href)
    with user_reader:
        container_push_repository_version_api.read(repository.latest_version_href)
    with user_helpless, pytest.raises(ApiException):
        container_push_repository_version_api.read(repository.latest_version_href)


def test_cross_repository_blob_mount(
    add_to_cleanup,
    gen_user,
    registry_client,
    local_registry,
    mount_blob,
    container_push_repository_api,
    container_distribution_api,
    container_namespace_api,
    container_blob_api,
    gen_object_with_cleanup,
):
    """Test that users can cross mount blobs from different repositories."""
    if TOKEN_AUTH_DISABLED:
        pytest.skip("Cannot test blob mounting without token authentication.")

    source_repo = utils.uuid4()
    dest_repo = utils.uuid4()
    local_url = f"{source_repo}:manifest_a"
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    registry_client.pull(image_path)
    local_registry.tag_and_push(image_path, local_url)
    repository = container_push_repository_api.list(name=source_repo).results[0]
    blobs = container_blob_api.list(repository_version=repository.latest_version_href).results
    distribution = container_distribution_api.list(name=source_repo).results[0]
    monitor_task(
        container_distribution_api.partial_update(distribution.pulp_href, {"private": True}).task
    )

    # Cleanup
    add_to_cleanup(container_namespace_api, distribution.namespace)

    # Test that an admin can cross mount but do not perform any further assertions because
    # the blobs are committed only after uploading the final tagged manifest
    for blob in blobs:
        content_response, auth_token = mount_blob(blob, source_repo, dest_repo)
        assert content_response.status_code == 201
        assert content_response.text == ""

        blob_url = f"/v2/{dest_repo}/blobs/{blob.digest}"
        response, _ = local_registry.get_response("GET", blob_url)
        assert response.status_code == 200

    try:
        distribution2 = container_distribution_api.list(name=dest_repo).results[0]
        monitor_task(container_distribution_api.delete(distribution2.pulp_href).task)
    except ValueError:
        pass

    user_consumer = gen_user(
        object_roles=[("container.containernamespace_consumer", distribution.namespace)]
    )
    user_collaborator = gen_user(
        object_roles=[("container.containernamespace_collaborator", distribution.namespace)]
    )
    user_helpless = gen_user()

    # Test if a user with pull permission, but not push permission, is not able to mount.
    with user_consumer:
        content_response, _ = mount_blob(blobs[0], source_repo, dest_repo)
        assert content_response.status_code == 401

    # Test if a collaborator cannot mount content outside his scope.
    with user_collaborator:
        content_response, _ = mount_blob(blobs[0], source_repo, dest_repo)
        assert content_response.status_code == 401

    # Test if an anonymous user with no permissions is not able to mount.
    with user_helpless:
        content_response, _ = mount_blob(blobs[0], source_repo, dest_repo)
        assert content_response.status_code == 401

    # Test if an owner of another namespace cannot utilize the blob mounting because of
    # insufficient permissions
    dest_tester_namespace = utils.uuid4()
    tester_namespace = gen_object_with_cleanup(
        container_namespace_api, {"name": dest_tester_namespace}
    )
    tester_owner = gen_user(
        object_roles=[("container.containernamespace_owner", tester_namespace.pulp_href)]
    )
    with tester_owner:
        local_registry.tag_and_push(image_path, f"{tester_namespace.name}/test:manifest_a")
        content_response, auth = mount_blob(blobs[0], source_repo, f"{dest_tester_namespace}/test")
        assert content_response.status_code == 401


@pytest.fixture
def mount_blob(local_registry, container_distribution_api, container_namespace_api, add_to_cleanup):
    """A fixture function to mount blobs to new repositories that will be cleaned up."""

    def _mount_blob(blob, source, dest):
        mount_path = f"/v2/{dest}/blobs/uploads/?from={source}&mount={blob.digest}"
        response, auth = local_registry.get_response("POST", mount_path)

        if response.status_code == 201:
            distribution = container_distribution_api.list(name=dest).results[0]
            add_to_cleanup(container_namespace_api, distribution.namespace)

        return response, auth

    return _mount_blob

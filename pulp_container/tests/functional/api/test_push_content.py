"""Tests that verify that images can be pushed to Pulp."""

import json
import pytest
import requests

from subprocess import CalledProcessError
from urllib.parse import urljoin

from pulp_container.constants import MEDIA_TYPE, MANIFEST_TYPE

from pulp_container.tests.functional.constants import REGISTRY_V2_REPO_PULP
from pulp_container.tests.functional.utils import get_auth_for_url


def test_push_using_registry_client_admin(
    add_to_cleanup,
    check_manifest_arch_os_size,
    registry_client,
    local_registry,
    check_manifest_fields,
    container_bindings,
    full_path,
):
    """Test push with official registry client and logged in as admin."""
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    local_url = full_path("foo/bar:1.0")

    registry_client.pull(image_path)
    local_registry.tag_and_push(image_path, local_url)
    local_registry.pull(local_url)

    # check pulp manifest model fields
    local_image = local_registry.inspect(local_url)
    assert check_manifest_fields(
        manifest_filters={"digest": local_image[0]["Digest"]},
        fields={"type": MANIFEST_TYPE.IMAGE},
    )
    manifest = container_bindings.ContentManifestsApi.list(digest=local_image[0]["Digest"])
    check_manifest_arch_os_size(manifest)

    # ensure that same content can be pushed twice without permission errors
    local_registry.tag_and_push(image_path, local_url)

    # cleanup, namespace removal also removes related distributions
    namespace = container_bindings.PulpContainerNamespacesApi.list(name="foo").results[0]
    add_to_cleanup(container_bindings.PulpContainerNamespacesApi, namespace.pulp_href)


def test_push_without_login(
    anonymous_user,
    registry_client,
    local_registry,
    full_path,
):
    """Test that one can't push without being logged in."""
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    local_url = full_path("foo/bar:1.0")
    registry_client.pull(image_path)

    # Try to push without permission
    with anonymous_user, pytest.raises(CalledProcessError):
        local_registry.tag_and_push(image_path, local_url)


def test_push_with_dist_perms(
    add_to_cleanup,
    gen_user,
    registry_client,
    local_registry,
    container_bindings,
    full_path,
    pulp_settings,
):
    """
    Test that it's enough to have container distribution and namespace perms to perform push.

    It also checks read abilities for users with different set of permissions.
    """
    if pulp_settings.TOKEN_AUTH_DISABLED:
        pytest.skip("RBAC cannot be tested when token authentication is disabled")

    user_creator = gen_user(model_roles=["container.containernamespace_creator"])
    user_dist_collaborator = gen_user()
    user_dist_consumer = gen_user()
    user_namespace_collaborator = gen_user()
    user_reader = gen_user()
    user_helpless = gen_user()

    repo_name = "test/perms"
    local_url = full_path(f"{repo_name}:2.0")
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    registry_client.pull(image_path)
    with user_creator:
        local_registry.tag_and_push(image_path, local_url)

    # cleanup, namespace removal also removes related distributions
    namespace = container_bindings.PulpContainerNamespacesApi.list(name="test").results[0]
    add_to_cleanup(container_bindings.PulpContainerNamespacesApi, namespace.pulp_href)

    with user_creator:
        distributions = container_bindings.DistributionsContainerApi.list(name="test/perms")
        distribution = distributions.results[0]
        container_bindings.DistributionsContainerApi.add_role(
            distribution.pulp_href,
            {
                "role": "container.containerdistribution_collaborator",
                "users": [user_dist_collaborator.username],
            },
        )
        container_bindings.DistributionsContainerApi.add_role(
            distribution.pulp_href,
            {
                "role": "container.containerdistribution_consumer",
                "users": [user_dist_consumer.username],
            },
        )
        container_bindings.PulpContainerNamespacesApi.add_role(
            distribution.namespace,
            {
                "role": "container.containernamespace_collaborator",
                "users": [user_namespace_collaborator.username],
            },
        )

    assert container_bindings.RepositoriesContainerPushApi.list(name=repo_name).count == 1
    with user_creator:
        assert container_bindings.RepositoriesContainerPushApi.list(name=repo_name).count == 1
    with user_dist_collaborator:
        assert container_bindings.RepositoriesContainerPushApi.list(name=repo_name).count == 1
    with user_dist_consumer:
        assert container_bindings.RepositoriesContainerPushApi.list(name=repo_name).count == 1
    with user_namespace_collaborator:
        assert container_bindings.RepositoriesContainerPushApi.list(name=repo_name).count == 1
    with user_reader:
        assert container_bindings.RepositoriesContainerPushApi.list(name=repo_name).count == 1
    with user_helpless:
        # "{repo_name}" turns out to be a public repository
        assert container_bindings.RepositoriesContainerPushApi.list(name=repo_name).count == 1


def test_push_with_view_perms(
    gen_user,
    registry_client,
    local_registry,
    full_path,
):
    """
    Test that push is not working if a user has only view permission for push repos.
    """
    user_reader = gen_user(model_roles=["container.containernamespace_consumer"])
    repo_name = "unsuccessful/perms"
    local_url = full_path(f"{repo_name}:2.0")
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    registry_client.pull(image_path)
    with user_reader, pytest.raises(CalledProcessError):
        local_registry.tag_and_push(image_path, local_url)


def test_push_with_no_perms(
    add_to_cleanup,
    gen_user,
    registry_client,
    local_registry,
    container_bindings,
    pulp_settings,
    full_path,
):
    """
    Test that user with no permissions can't perform push.
    """
    user_helpless = gen_user()
    repo_name = "unsuccessful/perms"
    local_url = full_path(f"{repo_name}:2.0")
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    registry_client.pull(image_path)
    with user_helpless, pytest.raises(CalledProcessError):
        local_registry.tag_and_push(image_path, local_url)

    # test if the helpless user can still pull
    if pulp_settings.TOKEN_AUTH_DISABLED:
        # push by using the admin user
        local_registry.tag_and_push(image_path, local_url)
        namespace = container_bindings.PulpContainerNamespacesApi.list(name="unsuccessful").results[
            0
        ]
        add_to_cleanup(container_bindings.PulpContainerNamespacesApi, namespace.pulp_href)

        with user_helpless:
            with pytest.raises(CalledProcessError):
                local_registry.tag_and_push(image_path, local_url)
            local_registry.pull(local_url)

        # flagging the repository as "private" does not have an effect on pulling
        distribution = container_bindings.DistributionsContainerApi.list(name=repo_name).results[0]
        container_bindings.DistributionsContainerApi.partial_update(
            distribution.pulp_href, {"private": True}
        )
        with user_helpless:
            local_registry.pull(local_url)
    else:
        # push by using the creator user
        user_creator = gen_user(model_roles=["container.containernamespace_creator"])
        with user_creator:
            local_registry.tag_and_push(image_path, local_url)
            namespace = container_bindings.PulpContainerNamespacesApi.list(
                name="unsuccessful"
            ).results[0]
            add_to_cleanup(container_bindings.PulpContainerNamespacesApi, namespace.pulp_href)

        with user_helpless:
            with pytest.raises(CalledProcessError):
                local_registry.tag_and_push(image_path, local_url)
            local_registry.pull(local_url)


def test_push_to_existing_namespace(
    add_to_cleanup,
    gen_user,
    registry_client,
    local_registry,
    container_bindings,
    pulp_settings,
    full_path,
):
    """
    Test the push to an existing namespace with collaborator permissions.

    Container distribution perms and manage-namespace one should be enough
    to push a new distribution.
    Container distribution perms should be enough to push to the existing
    distribution.
    """
    if pulp_settings.TOKEN_AUTH_DISABLED:
        pytest.skip("RBAC cannot be tested when token authentication is disabled")

    user_creator = gen_user(model_roles=["container.containernamespace_creator"])
    user_dist_collaborator = gen_user()
    user_namespace_collaborator = gen_user()
    repo_name = "team/owner"
    local_url = full_path(f"{repo_name}:2.0")
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    registry_client.pull(image_path)
    with user_creator:
        local_registry.tag_and_push(image_path, local_url)
        namespace = container_bindings.PulpContainerNamespacesApi.list(name="team").results[0]
        add_to_cleanup(container_bindings.PulpContainerNamespacesApi, namespace.pulp_href)

        # Add user_dist_collaborator to the collaborator group
        distributions = container_bindings.DistributionsContainerApi.list(name="team/owner")
        distribution = distributions.results[0]
        container_bindings.DistributionsContainerApi.add_role(
            distribution.pulp_href,
            {
                "role": "container.containerdistribution_collaborator",
                "users": [user_dist_collaborator.username],
            },
        )

    collab_repo_name = "team/owner"
    local_url = full_path(f"{collab_repo_name}:2.0")
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_b"
    registry_client.pull(image_path)
    with user_dist_collaborator:
        local_registry.tag_and_push(image_path, local_url)

    collab_repo_name = "team/collab"
    local_url = full_path(f"{collab_repo_name}:2.0")
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_d"
    registry_client.pull(image_path)
    with user_dist_collaborator, pytest.raises(CalledProcessError):
        local_registry.tag_and_push(image_path, local_url)

    with user_creator:
        container_bindings.PulpContainerNamespacesApi.add_role(
            distribution.namespace,
            {
                "role": "container.containernamespace_collaborator",
                "users": [user_namespace_collaborator.username],
            },
        )

    collab_repo_name = "team/collab"
    local_url = full_path(f"{collab_repo_name}:2.0")
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_c"
    registry_client.pull(image_path)
    with user_namespace_collaborator:
        local_registry.tag_and_push(image_path, local_url)


def test_push_private_repository(
    add_to_cleanup,
    gen_user,
    registry_client,
    local_registry,
    container_bindings,
    monitor_task,
    pulp_settings,
    full_path,
):
    """
    Test that you can create a private distribution and push to it.
    Test that the same user can pull, but another cannot.
    Test that the other user can pull after marking it non-private.
    """
    if pulp_settings.TOKEN_AUTH_DISABLED:
        pytest.skip("RBAC cannot be tested when token authentication is disabled")

    user_creator = gen_user(model_roles=["container.containernamespace_creator"])
    user_dist_consumer = gen_user()
    user_helpless = gen_user()
    repo_name = "test/private"
    local_url = full_path(f"{repo_name}:2.0")
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"

    distribution = {"name": repo_name, "base_path": repo_name, "private": True}
    registry_client.pull(image_path)
    with user_creator:
        distribution_response = container_bindings.DistributionsContainerApi.create(distribution)
        created_resources = monitor_task(distribution_response.task).created_resources
        distribution = container_bindings.DistributionsContainerApi.read(created_resources[0])
        add_to_cleanup(container_bindings.PulpContainerNamespacesApi, distribution.namespace)

        local_registry.tag_and_push(image_path, local_url)
        local_registry.pull(local_url)

        container_bindings.DistributionsContainerApi.add_role(
            distribution.pulp_href,
            {
                "role": "container.containerdistribution_consumer",
                "users": [user_dist_consumer.username],
            },
        )

    with user_dist_consumer:
        local_registry.pull(local_url)
    with user_helpless, pytest.raises(CalledProcessError):
        local_registry.pull(local_url)

    with user_creator:
        distribution.private = False
        distribution_response = container_bindings.DistributionsContainerApi.partial_update(
            distribution.pulp_href, {"private": False}
        )
        monitor_task(distribution_response.task)

    with user_helpless:
        local_registry.pull(local_url)


def test_push_matching_username(
    add_to_cleanup,
    gen_user,
    registry_client,
    local_registry,
    container_bindings,
    monitor_task,
    pulp_settings,
    full_path,
):
    """
    Test that you can push to a nonexisting namespace that matches your username.
    """
    if pulp_settings.TOKEN_AUTH_DISABLED:
        pytest.skip("RBAC cannot be tested when token authentication is disabled")

    user_helpless = gen_user()
    namespace_name = user_helpless.username
    repo_name = f"{namespace_name}/matching"
    local_url = full_path(f"{repo_name}:2.0")
    invalid_local_url = full_path(f"other/{repo_name}:2.0")
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"

    registry_client.pull(image_path)
    with user_helpless:
        local_registry.tag_and_push(image_path, local_url)
        namespace = container_bindings.PulpContainerNamespacesApi.list(name=namespace_name).results[
            0
        ]
        add_to_cleanup(container_bindings.PulpContainerNamespacesApi, namespace.pulp_href)

        with pytest.raises(CalledProcessError):
            local_registry.tag_and_push(image_path, invalid_local_url)

        # test you can create distribution under the namespace that matches login
        repo_name2 = f"{namespace_name}/matching2"
        distribution = {"name": repo_name2, "base_path": repo_name2, "private": True}
        distribution_response = container_bindings.DistributionsContainerApi.create(distribution)
        created_resources = monitor_task(distribution_response.task).created_resources
        distribution = container_bindings.DistributionsContainerApi.read(created_resources[0])

        # cleanup, namespace removal also removes related distributions
        namespace_response = container_bindings.PulpContainerNamespacesApi.delete(
            namespace.pulp_href
        )
        monitor_task(namespace_response.task)

        # test you can create distribution if namespace does not exist but matches login
        distribution = {"name": repo_name, "base_path": repo_name, "private": True}
        distribution_response = container_bindings.DistributionsContainerApi.create(distribution)
        created_resources = monitor_task(distribution_response.task).created_resources
        distribution = container_bindings.DistributionsContainerApi.read(created_resources[0])

        add_to_cleanup(container_bindings.PulpContainerNamespacesApi, distribution.namespace)


def test_push_to_existing_regular_repository(
    container_repository_factory,
    local_registry,
    registry_client,
    full_path,
):
    """
    Test the push to an existing non-push repository.

    It should fail to create a new push repository.
    """
    container_repository_factory(name="foo")
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    local_url = full_path("foo:1.0")

    registry_client.pull(image_path)
    with pytest.raises(CalledProcessError):
        local_registry.tag_and_push(image_path, local_url)


class TestPushManifestList:
    """A test case that verifies if a container client can push manifest lists to the registry."""

    manifest_a = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    manifest_b = f"{REGISTRY_V2_REPO_PULP}:manifest_b"
    manifest_c = f"{REGISTRY_V2_REPO_PULP}:manifest_c"
    v2s2_tag = "manifest_list"
    v2s2_image_path = f"foo_v2s2:{v2s2_tag}"
    oci_tag = "manifest_list_oci"
    oci_image_path = f"foo_oci:{oci_tag}"
    empty_image_tag = "empty_manifest_list"
    empty_image_path = f"foo_empty:{empty_image_tag}"

    @pytest.fixture(scope="class", autouse=True)
    def setup(self, registry_client):
        """Initialize a new manifest list that will be pushed to the registry."""
        registry_client.pull(self.manifest_a)
        registry_client.pull(self.manifest_b)
        registry_client.pull(self.manifest_c)

        # create a new manifest list composed of the pulled manifest images
        registry_client._dispatch_command("manifest", "create", self.v2s2_tag)
        registry_client._dispatch_command("manifest", "add", self.v2s2_tag, self.manifest_a)
        registry_client._dispatch_command("manifest", "add", self.v2s2_tag, self.manifest_b)
        registry_client._dispatch_command("manifest", "add", self.v2s2_tag, self.manifest_c)

        # create a new manifest list composed of the pulled manifest images
        registry_client._dispatch_command("manifest", "create", self.oci_tag)
        registry_client._dispatch_command("manifest", "add", self.oci_tag, self.manifest_a)
        registry_client._dispatch_command("manifest", "add", self.oci_tag, self.manifest_b)
        registry_client._dispatch_command("manifest", "add", self.oci_tag, self.manifest_c)

        # create an empty manifest list
        registry_client._dispatch_command("manifest", "create", self.empty_image_tag)

        yield

        registry_client._dispatch_command("manifest", "rm", self.v2s2_tag)
        registry_client._dispatch_command("manifest", "rm", self.oci_tag)
        registry_client._dispatch_command("manifest", "rm", self.empty_image_tag)

        registry_client._dispatch_command("image", "rm", self.manifest_a)
        registry_client._dispatch_command("image", "rm", self.manifest_b)
        registry_client._dispatch_command("image", "rm", self.manifest_c)

    def test_push_manifest_list_v2s2(
        self, local_registry, container_bindings, add_to_cleanup, full_path
    ):
        """Push the created manifest list in the v2s2 format."""
        local_registry.manifest_push(
            self.v2s2_tag,
            full_path(self.v2s2_image_path),
            "--all",
            "--format",
            "v2s2",
        )

        # pushing the same manifest list two times should not fail
        local_registry.manifest_push(
            self.v2s2_tag,
            full_path(self.v2s2_image_path),
            "--all",
            "--format",
            "v2s2",
        )

        distribution = container_bindings.DistributionsContainerApi.list(name="foo_v2s2").results[0]
        add_to_cleanup(container_bindings.DistributionsContainerApi, distribution.pulp_href)

        repo_version = container_bindings.RepositoriesContainerPushApi.read(
            distribution.repository
        ).latest_version_href

        tags = container_bindings.ContentTagsApi.list(repository_version=repo_version).results
        assert len(tags) == 1

        latest_tag = tags[0]
        assert latest_tag.name == self.v2s2_tag

        manifest_list = container_bindings.ContentManifestsApi.read(latest_tag.tagged_manifest)
        assert manifest_list.media_type == MEDIA_TYPE.MANIFEST_LIST
        assert manifest_list.schema_version == 2

        # load manifest_list.json
        image_path = "/v2/{}/manifests/{}".format(full_path(distribution), latest_tag.name)
        latest_image_url = urljoin(container_bindings.client.configuration.host, image_path)

        auth = get_auth_for_url(latest_image_url)
        content_response = requests.get(
            latest_image_url, auth=auth, headers={"Accept": MEDIA_TYPE.MANIFEST_LIST}
        )
        content_response.raise_for_status()
        ml_json = json.loads(content_response.content)
        manifests = ml_json.get("manifests")
        manifests_v2s2_digests = sorted([manifest["digest"] for manifest in manifests])

        referenced_manifests_digests = sorted(
            [
                container_bindings.ContentManifestsApi.read(manifest_href).digest
                for manifest_href in manifest_list.listed_manifests
            ]
        )
        assert referenced_manifests_digests == manifests_v2s2_digests

        local_registry.pull(full_path(self.v2s2_image_path))

    def test_push_manifest_list_oci(
        self, local_registry, container_bindings, add_to_cleanup, full_path
    ):
        """Push the created manifest list in the OCI format."""
        local_registry.manifest_push(
            self.oci_tag,
            full_path(self.oci_image_path),
            "--all",
            "--format",
            "oci",
        )

        distribution = container_bindings.DistributionsContainerApi.list(name="foo_oci").results[0]
        add_to_cleanup(container_bindings.DistributionsContainerApi, distribution.pulp_href)

        repo_version = container_bindings.RepositoriesContainerPushApi.read(
            distribution.repository
        ).latest_version_href

        tags = container_bindings.ContentTagsApi.list(repository_version=repo_version).results
        assert len(tags) == 1

        latest_tag = tags[0]
        assert latest_tag.name == self.oci_tag

        manifest_list = container_bindings.ContentManifestsApi.read(latest_tag.tagged_manifest)
        assert manifest_list.media_type == MEDIA_TYPE.INDEX_OCI
        assert manifest_list.schema_version == 2

        # load manifest_list.json
        image_path = "/v2/{}/manifests/{}".format(full_path(distribution), latest_tag.name)
        latest_image_url = urljoin(container_bindings.client.configuration.host, image_path)

        auth = get_auth_for_url(latest_image_url)
        content_response = requests.get(
            latest_image_url, auth=auth, headers={"Accept": MEDIA_TYPE.INDEX_OCI}
        )
        content_response.raise_for_status()
        ml_json = json.loads(content_response.content)
        manifests = ml_json.get("manifests")
        manifests_oci_digests = sorted([manifest["digest"] for manifest in manifests])

        referenced_manifests_digests = sorted(
            [
                container_bindings.ContentManifestsApi.read(manifest_href).digest
                for manifest_href in manifest_list.listed_manifests
            ]
        )
        assert referenced_manifests_digests == manifests_oci_digests

        local_registry.pull(full_path(self.oci_image_path))

    def test_push_empty_manifest_list(
        self, local_registry, container_bindings, add_to_cleanup, full_path
    ):
        """Push an empty manifest list to the registry."""
        local_registry.manifest_push(self.empty_image_tag, full_path(self.empty_image_path))

        distribution = container_bindings.DistributionsContainerApi.list(name="foo_empty").results[
            0
        ]
        add_to_cleanup(container_bindings.DistributionsContainerApi, distribution.pulp_href)

        repo_version = container_bindings.RepositoriesContainerPushApi.read(
            distribution.repository
        ).latest_version_href
        latest_tag = container_bindings.ContentTagsApi.list(
            repository_version_added=repo_version
        ).results[0]
        assert latest_tag.name == self.empty_image_tag

        manifest_list = container_bindings.ContentManifestsApi.read(latest_tag.tagged_manifest)
        # empty manifest lists are being pushed in the v2s2 format by default
        assert manifest_list.media_type == MEDIA_TYPE.MANIFEST_LIST
        assert manifest_list.schema_version == 2
        assert manifest_list.listed_manifests == []

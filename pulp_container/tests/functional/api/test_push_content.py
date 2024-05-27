"""Tests that verify that images can be pushed to Pulp."""

import json
import pytest
import requests
import unittest

from django.conf import settings

from subprocess import CalledProcessError
from urllib.parse import urlparse, urljoin

from pulp_smash import cli, config
from pulp_smash.pulp3.bindings import (
    delete_orphans,
    monitor_task,
    PulpTestCase,
)

from pulp_container.constants import MEDIA_TYPE

from pulp_container.tests.functional.api import rbac_base
from pulp_container.tests.functional.constants import REGISTRY_V2_REPO_PULP
from pulp_container.tests.functional.utils import (
    gen_container_client,
    get_auth_for_url,
)

from pulpcore.client.pulp_container import (
    ContentManifestsApi,
    ContentTagsApi,
    DistributionsContainerApi,
    RepositoriesContainerPushApi,
)


def test_push_using_registry_client_admin(
    add_to_cleanup,
    registry_client,
    local_registry,
    container_namespace_api,
):
    """Test push with official registry client and logged in as admin."""
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    local_url = "foo/bar:1.0"

    registry_client.pull(image_path)
    local_registry.tag_and_push(image_path, local_url)
    local_registry.pull(local_url)
    # ensure that same content can be pushed twice without permission errors
    local_registry.tag_and_push(image_path, local_url)

    # cleanup, namespace removal also removes related distributions
    namespace = container_namespace_api.list(name="foo").results[0]
    add_to_cleanup(container_namespace_api, namespace.pulp_href)


def test_push_without_login(
    anonymous_user,
    registry_client,
    local_registry,
):
    """Test that one can't push without being logged in."""
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    local_url = "foo/bar:1.0"
    registry_client.pull(image_path)

    # Try to push without permission
    with anonymous_user, pytest.raises(CalledProcessError):
        local_registry.tag_and_push(image_path, local_url)


def test_push_with_dist_perms(
    add_to_cleanup,
    gen_user,
    registry_client,
    local_registry,
    container_push_repository_api,
    container_distribution_api,
    container_namespace_api,
):
    """
    Test that it's enough to have container distribution and namespace perms to perform push.

    It also checks read abilities for users with different set of permissions.
    """
    if settings.TOKEN_AUTH_DISABLED:
        pytest.skip("RBAC cannot be tested when token authentication is disabled")

    user_creator = gen_user(model_roles=["container.containernamespace_creator"])
    user_dist_collaborator = gen_user()
    user_dist_consumer = gen_user()
    user_namespace_collaborator = gen_user()
    user_reader = gen_user()
    user_helpless = gen_user()

    repo_name = "test/perms"
    local_url = f"{repo_name}:2.0"
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    registry_client.pull(image_path)
    with user_creator:
        local_registry.tag_and_push(image_path, local_url)

    # cleanup, namespace removal also removes related distributions
    namespace = container_namespace_api.list(name="test").results[0]
    add_to_cleanup(container_namespace_api, namespace.pulp_href)

    with user_creator:
        distributions = container_distribution_api.list(name="test/perms")
        distribution = distributions.results[0]
        container_distribution_api.add_role(
            distribution.pulp_href,
            {
                "role": "container.containerdistribution_collaborator",
                "users": [user_dist_collaborator.username],
            },
        )
        container_distribution_api.add_role(
            distribution.pulp_href,
            {
                "role": "container.containerdistribution_consumer",
                "users": [user_dist_consumer.username],
            },
        )
        container_distribution_api.add_role(
            distribution.namespace,
            {
                "role": "container.containernamespace_collaborator",
                "users": [user_namespace_collaborator.username],
            },
        )

    assert container_push_repository_api.list(name=repo_name).count == 1
    with user_creator:
        assert container_push_repository_api.list(name=repo_name).count == 1
    with user_dist_collaborator:
        assert container_push_repository_api.list(name=repo_name).count == 1
    with user_dist_consumer:
        assert container_push_repository_api.list(name=repo_name).count == 1
    with user_namespace_collaborator:
        assert container_push_repository_api.list(name=repo_name).count == 1
    with user_reader:
        assert container_push_repository_api.list(name=repo_name).count == 1
    with user_helpless:
        # "{repo_name}" turns out to be a public repository
        assert container_push_repository_api.list(name=repo_name).count == 1


def test_push_with_view_perms(
    gen_user,
    registry_client,
    local_registry,
):
    """
    Test that push is not working if a user has only view permission for push repos.
    """
    user_reader = gen_user(model_roles=["container.containernamespace_consumer"])
    repo_name = "unsuccessful/perms"
    local_url = f"{repo_name}:2.0"
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    registry_client.pull(image_path)
    with user_reader, pytest.raises(CalledProcessError):
        local_registry.tag_and_push(image_path, local_url)


def test_push_with_no_perms(
    add_to_cleanup,
    gen_user,
    registry_client,
    local_registry,
    container_distribution_api,
    container_namespace_api,
):
    """
    Test that user with no permissions can't perform push.
    """
    user_helpless = gen_user()
    repo_name = "unsuccessful/perms"
    local_url = f"{repo_name}:2.0"
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    registry_client.pull(image_path)
    with user_helpless, pytest.raises(CalledProcessError):
        local_registry.tag_and_push(image_path, local_url)

    # test if the helpless user can still pull
    if settings.TOKEN_AUTH_DISABLED:
        # push by using the admin user
        local_registry.tag_and_push(image_path, local_url)
        namespace = container_namespace_api.list(name="unsuccessful").results[0]
        add_to_cleanup(container_namespace_api, namespace.pulp_href)

        with user_helpless:
            with pytest.raises(CalledProcessError):
                local_registry.tag_and_push(image_path, local_url)
            local_registry.pull(local_url)

        # flagging the repository as "private" does not have an effect on pulling
        distribution = container_distribution_api.list(name=repo_name).results[0]
        container_distribution_api.partial_update(distribution.pulp_href, {"private": True})
        with user_helpless:
            local_registry.pull(local_url)
    else:
        # push by using the creator user
        user_creator = gen_user(model_roles=["container.containernamespace_creator"])
        with user_creator:
            local_registry.tag_and_push(image_path, local_url)
            namespace = container_namespace_api.list(name="unsuccessful").results[0]
            add_to_cleanup(container_namespace_api, namespace.pulp_href)

        with user_helpless:
            with pytest.raises(CalledProcessError):
                local_registry.tag_and_push(image_path, local_url)
            local_registry.pull(local_url)


def test_push_to_existing_namespace(
    add_to_cleanup,
    gen_user,
    registry_client,
    local_registry,
    container_distribution_api,
    container_namespace_api,
):
    """
    Test the push to an existing namespace with collaborator permissions.

    Container distribution perms and manage-namespace one should be enough
    to push a new distribution.
    Container distribution perms should be enough to push to the existing
    distribution.
    """
    if settings.TOKEN_AUTH_DISABLED:
        pytest.skip("RBAC cannot be tested when token authentication is disabled")

    user_creator = gen_user(model_roles=["container.containernamespace_creator"])
    user_dist_collaborator = gen_user()
    user_namespace_collaborator = gen_user()
    repo_name = "team/owner"
    local_url = f"{repo_name}:2.0"
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    registry_client.pull(image_path)
    with user_creator:
        local_registry.tag_and_push(image_path, local_url)
        namespace = container_namespace_api.list(name="team").results[0]
        add_to_cleanup(container_namespace_api, namespace.pulp_href)

        # Add user_dist_collaborator to the collaborator group
        distributions = container_distribution_api.list(name="team/owner")
        distribution = distributions.results[0]
        container_distribution_api.add_role(
            distribution.pulp_href,
            {
                "role": "container.containerdistribution_collaborator",
                "users": [user_dist_collaborator.username],
            },
        )

    collab_repo_name = "team/owner"
    local_url = f"{collab_repo_name}:2.0"
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_b"
    registry_client.pull(image_path)
    with user_dist_collaborator:
        local_registry.tag_and_push(image_path, local_url)

    collab_repo_name = "team/collab"
    local_url = f"{collab_repo_name}:2.0"
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_d"
    registry_client.pull(image_path)
    with user_dist_collaborator, pytest.raises(CalledProcessError):
        local_registry.tag_and_push(image_path, local_url)

    with user_creator:
        container_namespace_api.add_role(
            distribution.namespace,
            {
                "role": "container.containernamespace_collaborator",
                "users": [user_namespace_collaborator.username],
            },
        )

    collab_repo_name = "team/collab"
    local_url = f"{collab_repo_name}:2.0"
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_c"
    registry_client.pull(image_path)
    with user_namespace_collaborator:
        local_registry.tag_and_push(image_path, local_url)


def test_push_private_repository(
    add_to_cleanup,
    gen_user,
    registry_client,
    local_registry,
    container_distribution_api,
    container_namespace_api,
):
    """
    Test that you can create a private distribution and push to it.
    Test that the same user can pull, but another cannot.
    Test that the other user can pull after marking it non-private.
    """
    if settings.TOKEN_AUTH_DISABLED:
        pytest.skip("RBAC cannot be tested when token authentication is disabled")

    user_creator = gen_user(model_roles=["container.containernamespace_creator"])
    user_dist_consumer = gen_user()
    user_helpless = gen_user()
    repo_name = "test/private"
    local_url = f"{repo_name}:2.0"
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"

    distribution = {"name": repo_name, "base_path": repo_name, "private": True}
    registry_client.pull(image_path)
    with user_creator:
        distribution_response = container_distribution_api.create(distribution)
        created_resources = monitor_task(distribution_response.task).created_resources
        distribution = container_distribution_api.read(created_resources[0])
        add_to_cleanup(container_namespace_api, distribution.namespace)

        local_registry.tag_and_push(image_path, local_url)
        local_registry.pull(local_url)

        container_distribution_api.add_role(
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
        distribution_response = container_distribution_api.partial_update(
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
    container_distribution_api,
    container_namespace_api,
):
    """
    Test that you can push to a nonexisting namespace that matches your username.
    """
    if settings.TOKEN_AUTH_DISABLED:
        pytest.skip("RBAC cannot be tested when token authentication is disabled")

    user_helpless = gen_user()
    namespace_name = user_helpless.username
    repo_name = f"{namespace_name}/matching"
    local_url = f"{repo_name}:2.0"
    invalid_local_url = f"other/{repo_name}:2.0"
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"

    registry_client.pull(image_path)
    with user_helpless:
        local_registry.tag_and_push(image_path, local_url)
        namespace = container_namespace_api.list(name=namespace_name).results[0]
        add_to_cleanup(container_namespace_api, namespace.pulp_href)

        with pytest.raises(CalledProcessError):
            local_registry.tag_and_push(image_path, invalid_local_url)

        # test you can create distribution under the namespace that matches login
        repo_name2 = f"{namespace_name}/matching2"
        distribution = {"name": repo_name2, "base_path": repo_name2, "private": True}
        distribution_response = container_distribution_api.create(distribution)
        created_resources = monitor_task(distribution_response.task).created_resources
        distribution = container_distribution_api.read(created_resources[0])

        # cleanup, namespace removal also removes related distributions
        namespace_response = container_namespace_api.delete(namespace.pulp_href)
        monitor_task(namespace_response.task)

        # test you can create distribution if namespace does not exist but matches login
        distribution = {"name": repo_name, "base_path": repo_name, "private": True}
        distribution_response = container_distribution_api.create(distribution)
        created_resources = monitor_task(distribution_response.task).created_resources
        distribution = container_distribution_api.read(created_resources[0])

        add_to_cleanup(container_namespace_api, distribution.namespace)


class PushManifestListTestCase(PulpTestCase, rbac_base.BaseRegistryTest):
    """A test case that verifies if a container client can push manifest lists to the registry."""

    @classmethod
    def setUpClass(cls):
        """Initialize a new manifest list that will be pushed to the registry."""
        cls.cfg = config.get_config()
        cls.registry = cli.RegistryClient(cls.cfg)
        cls.registry.raise_if_unsupported(unittest.SkipTest, "Tests require podman/docker")
        cls.registry_name = urlparse(cls.cfg.get_base_url()).netloc

        admin_user, admin_password = cls.cfg.pulp_auth
        cls.registry.login("-u", admin_user, "-p", admin_password, cls.registry_name)
        cls.user_admin = {"username": admin_user, "password": admin_password}

        api_client = gen_container_client()
        api_client.configuration.username = cls.user_admin["username"]
        api_client.configuration.password = cls.user_admin["password"]
        cls.pushrepository_api = RepositoriesContainerPushApi(api_client)
        cls.distributions_api = DistributionsContainerApi(api_client)
        cls.manifests_api = ContentManifestsApi(api_client)
        cls.tags_api = ContentTagsApi(api_client)

        cls.manifest_a = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
        cls.manifest_b = f"{REGISTRY_V2_REPO_PULP}:manifest_b"
        cls.manifest_c = f"{REGISTRY_V2_REPO_PULP}:manifest_c"
        cls._pull(cls.manifest_a)
        cls._pull(cls.manifest_b)
        cls._pull(cls.manifest_c)

        # create a new manifest list composed of the pulled manifest images
        cls.v2s2_tag = "manifest_list"
        cls.v2s2_image_path = f"{cls.registry_name}/foo_v2s2:{cls.v2s2_tag}"
        cls.registry._dispatch_command("manifest", "create", cls.v2s2_tag)
        cls.registry._dispatch_command("manifest", "add", cls.v2s2_tag, cls.manifest_a)
        cls.registry._dispatch_command("manifest", "add", cls.v2s2_tag, cls.manifest_b)
        cls.registry._dispatch_command("manifest", "add", cls.v2s2_tag, cls.manifest_c)

        # create a new manifest list composed of the pulled manifest images
        cls.oci_tag = "manifest_list_oci"
        cls.oci_image_path = f"{cls.registry_name}/foo_oci:{cls.oci_tag}"
        cls.registry._dispatch_command("manifest", "create", cls.oci_tag)
        cls.registry._dispatch_command("manifest", "add", cls.oci_tag, cls.manifest_a)
        cls.registry._dispatch_command("manifest", "add", cls.oci_tag, cls.manifest_b)
        cls.registry._dispatch_command("manifest", "add", cls.oci_tag, cls.manifest_c)

        # create an empty manifest list
        cls.empty_image_tag = "empty_manifest_list"
        cls.empty_image_path = f"{cls.registry_name}/foo_empty:{cls.empty_image_tag}"
        cls.registry._dispatch_command("manifest", "create", cls.empty_image_tag)

    @classmethod
    def tearDownClass(cls):
        """Clean up created images."""
        cls.registry._dispatch_command("manifest", "rm", cls.v2s2_tag)
        cls.registry._dispatch_command("manifest", "rm", cls.oci_tag)
        cls.registry._dispatch_command("manifest", "rm", cls.empty_image_tag)

        cls.registry._dispatch_command("image", "rm", cls.manifest_a)
        cls.registry._dispatch_command("image", "rm", cls.manifest_b)
        cls.registry._dispatch_command("image", "rm", cls.manifest_c)

        delete_orphans()

    def test_push_manifest_list_v2s2(self):
        """Push the created manifest list in the v2s2 format."""
        self.registry.login(
            "-u", self.user_admin["username"], "-p", self.user_admin["password"], self.registry_name
        )
        self.registry.manifest_push(
            self.v2s2_tag,
            self.v2s2_image_path,
            "--all",
            "--format",
            "v2s2",
        )

        # pushing the same manifest list two times should not fail
        self.registry.manifest_push(
            self.v2s2_tag,
            self.v2s2_image_path,
            "--all",
            "--format",
            "v2s2",
        )

        distribution = self.distributions_api.list(name="foo_v2s2").results[0]
        self.addCleanup(self.distributions_api.delete, distribution.pulp_href)

        repo_version = self.pushrepository_api.read(distribution.repository).latest_version_href

        tags = self.tags_api.list(repository_version=repo_version).results
        assert len(tags) == 1

        latest_tag = tags[0]
        assert latest_tag.name == self.v2s2_tag

        manifest_list = self.manifests_api.read(latest_tag.tagged_manifest)
        assert manifest_list.media_type == MEDIA_TYPE.MANIFEST_LIST
        assert manifest_list.schema_version == 2

        # load manifest_list.json
        image_path = "/v2/{}/manifests/{}".format(distribution.base_path, latest_tag.name)
        latest_image_url = urljoin(self.cfg.get_base_url(), image_path)

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
                self.manifests_api.read(manifest_href).digest
                for manifest_href in manifest_list.listed_manifests
            ]
        )
        assert referenced_manifests_digests == manifests_v2s2_digests

        self.registry.pull(self.v2s2_image_path)

    def test_push_manifest_list_oci(self):
        """Push the created manifest list in the OCI format."""
        self.registry.login(
            "-u", self.user_admin["username"], "-p", self.user_admin["password"], self.registry_name
        )
        self.registry.manifest_push(
            self.oci_tag,
            self.oci_image_path,
            "--all",
            "--format",
            "oci",
        )

        distribution = self.distributions_api.list(name="foo_oci").results[0]
        self.addCleanup(self.distributions_api.delete, distribution.pulp_href)

        repo_version = self.pushrepository_api.read(distribution.repository).latest_version_href

        tags = self.tags_api.list(repository_version=repo_version).results
        assert len(tags) == 1

        latest_tag = tags[0]
        assert latest_tag.name == self.oci_tag

        manifest_list = self.manifests_api.read(latest_tag.tagged_manifest)
        assert manifest_list.media_type == MEDIA_TYPE.INDEX_OCI
        assert manifest_list.schema_version == 2

        # load manifest_list.json
        image_path = "/v2/{}/manifests/{}".format(distribution.base_path, latest_tag.name)
        latest_image_url = urljoin(self.cfg.get_base_url(), image_path)

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
                self.manifests_api.read(manifest_href).digest
                for manifest_href in manifest_list.listed_manifests
            ]
        )
        assert referenced_manifests_digests == manifests_oci_digests

        self.registry.pull(self.oci_image_path)

    def test_push_empty_manifest_list(self):
        """Push an empty manifest list to the registry."""
        self.registry.login(
            "-u", self.user_admin["username"], "-p", self.user_admin["password"], self.registry_name
        )
        self.registry.manifest_push(self.empty_image_tag, self.empty_image_path)

        distribution = self.distributions_api.list(name="foo_empty").results[0]
        self.addCleanup(self.distributions_api.delete, distribution.pulp_href)

        repo_version = self.pushrepository_api.read(distribution.repository).latest_version_href
        latest_tag = self.tags_api.list(repository_version_added=repo_version).results[0]
        assert latest_tag.name == self.empty_image_tag

        manifest_list = self.manifests_api.read(latest_tag.tagged_manifest)
        # empty manifest lists are being pushed in the v2s2 format by default
        assert manifest_list.media_type == MEDIA_TYPE.MANIFEST_LIST
        assert manifest_list.schema_version == 2
        assert manifest_list.listed_manifests == []

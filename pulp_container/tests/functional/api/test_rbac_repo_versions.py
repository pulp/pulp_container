# coding=utf-8
"""Tests that verify that RBAC for repository versions work properly."""
import requests
import unittest

from urllib.parse import urlparse, urljoin

from pulp_smash import api, cli, config
from pulp_smash.pulp3.bindings import delete_orphans, monitor_task, PulpTestCase
from pulp_smash.pulp3.utils import gen_repo

from pulpcore.client.pulp_container.exceptions import ApiException

from pulp_container.tests.functional.api import rbac_base
from pulp_container.tests.functional.constants import PULP_FIXTURE_1, REGISTRY_V2_REPO_PULP
from pulp_container.tests.functional.utils import (
    TOKEN_AUTH_DISABLED,
    del_user,
    gen_container_client,
    gen_container_remote,
    gen_user,
    BearerTokenAuth,
    AuthenticationHeaderQueries,
)

from pulpcore.client.pulp_container import (
    ContainerContainerRepository,
    ContentBlobsApi,
    ContentTagsApi,
    ContentManifestsApi,
    ContainerRepositorySyncURL,
    DistributionsContainerApi,
    PulpContainerNamespacesApi,
    RepositoriesContainerApi,
    RepositoriesContainerPushApi,
    RepositoriesContainerVersionsApi,
)

from .test_tagging_images import TaggingTestCommons


class SyncRepoVersionTestCase(unittest.TestCase, TaggingTestCommons):
    """Verify RBAC for repo versions of a ContainerRepository."""

    @classmethod
    def setUpClass(cls):
        """
        Define APIs to use and pull images needed later in tests
        """
        api_client = gen_container_client()
        cfg = config.get_config()

        cls.repositories_api = RepositoriesContainerApi(api_client)
        cls.repo_version_api = RepositoriesContainerVersionsApi(api_client)
        cls.tags_api = ContentTagsApi(api_client)
        cls.manifests_api = ContentManifestsApi(api_client)

        admin_user, admin_password = cfg.pulp_auth
        cls.user_admin = {"username": admin_user, "password": admin_password}
        cls.user_creator = gen_user(
            model_roles=[
                "container.containerrepository_creator",
                "container.containerremote_creator",
            ]
        )
        cls.user_repov_remover = gen_user(
            model_roles=[
                "container.containerrepository_content_manager",
            ]
        )
        # TODO: Not sure what is the right role for this user...
        cls.user_repo_remover = gen_user(
            model_roles=[
                "container.containerrepository_owner",
            ]
        )
        cls.user_reader = gen_user(model_roles=["container.containerrepository_viewer"])
        cls.user_helpless = gen_user()

        # sync a repo
        cls.repository = cls.user_creator["repository_api"].create(
            ContainerContainerRepository(**gen_repo())
        )
        cls.remote = cls.user_creator["remote_api"].create(
            gen_container_remote(upstream_name=PULP_FIXTURE_1)
        )
        sync_data = ContainerRepositorySyncURL(remote=cls.remote.pulp_href)
        sync_response = cls.user_creator["repository_api"].sync(cls.repository.pulp_href, sync_data)
        monitor_task(sync_response.task)

    @classmethod
    def tearDownClass(cls):
        """Delete api users and things created in setUpclass."""
        cls.user_creator["repository_api"].delete(cls.repository.pulp_href)
        cls.user_creator["remote_api"].delete(cls.remote.pulp_href)
        delete_orphans()
        del_user(cls.user_creator)
        del_user(cls.user_repov_remover)
        del_user(cls.user_repo_remover)
        del_user(cls.user_reader)
        del_user(cls.user_helpless)

    def test_repov_list(self):
        """
        Test that users can list repository versions if they have enough rights
        """
        self.assertEqual(self.repo_version_api.list(self.repository.pulp_href).count, 2)
        self.assertEqual(
            self.user_creator["repo_version_api"].list(self.repository.pulp_href).count, 2
        )
        self.assertEqual(
            self.user_reader["repo_version_api"].list(self.repository.pulp_href).count, 2
        )
        with self.assertRaises(ApiException):
            self.user_helpless["repo_version_api"].list(self.repository.pulp_href)

    def test_repov_read(self):
        """
        Test that users can read specific repository versions if they have enough rights
        """
        repository = self.repositories_api.read(self.repository.pulp_href)
        self.repo_version_api.read(repository.latest_version_href)
        self.user_creator["repo_version_api"].read(repository.latest_version_href)
        self.user_reader["repo_version_api"].read(repository.latest_version_href)
        with self.assertRaises(ApiException):
            self.user_helpless["repo_version_api"].read(repository.latest_version_href)

    def test_repov_delete(self):
        """
        Test that users can delete repository versions if they have enough rights
        """

        def create_new_repo_version():
            """
            Create a new repo version to delete it later by a test user
            """
            manifest_a = self.get_manifest_by_tag("manifest_a")
            self.tag_image(manifest_a, "new_tag")
            repository = self.repositories_api.read(self.repository.pulp_href)
            return repository.latest_version_href

        repository = self.repositories_api.read(self.repository.pulp_href)
        with self.assertRaises(ApiException):
            self.user_helpless["repo_version_api"].delete(repository.latest_version_href)
        with self.assertRaises(ApiException):
            self.user_reader["repo_version_api"].delete(repository.latest_version_href)

        response = self.repo_version_api.delete(create_new_repo_version())
        monitor_task(response.task)

        response = self.user_creator["repo_version_api"].delete(create_new_repo_version())
        monitor_task(response.task)

        response = self.user_repov_remover["repo_version_api"].delete(create_new_repo_version())
        monitor_task(response.task)

        response = self.user_repo_remover["repo_version_api"].delete(create_new_repo_version())
        monitor_task(response.task)


class PushRepoVersionTestCase(unittest.TestCase, rbac_base.BaseRegistryTest):
    """Verify RBAC for repo versions of a ContainerPushRepository."""

    @classmethod
    def setUpClass(cls):
        """
        Define APIs to use and pull images needed later in tests
        """
        api_client = gen_container_client()
        cls.pushrepository_api = RepositoriesContainerPushApi(api_client)
        cls.namespace_api = PulpContainerNamespacesApi(api_client)
        cls.repo_version_api = RepositoriesContainerVersionsApi(api_client)

        cfg = config.get_config()
        cls.registry = cli.RegistryClient(cfg)
        cls.registry.raise_if_unsupported(unittest.SkipTest, "Tests require podman/docker")
        cls.registry_name = urlparse(cfg.get_base_url()).netloc

        admin_user, admin_password = cfg.pulp_auth
        cls.user_admin = {"username": admin_user, "password": admin_password}
        cls.user_creator = gen_user(
            model_roles=[
                "container.containernamespace_creator",
            ]
        )
        cls.user_reader = gen_user(model_roles=["container.containerdistribution_consumer"])
        cls.user_helpless = gen_user()

        # create a push repo
        image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_d"
        cls._pull(image_path)
        repo_name = "testrv/perms"
        local_url = "/".join([cls.registry_name, f"{repo_name}:1.0"])
        cls._push(image_path, local_url, cls.user_creator)
        cls.repository = cls.pushrepository_api.list(name=repo_name).results[0]

    @classmethod
    def tearDownClass(cls):
        """Delete api users and things created in setUpclass."""
        namespace = cls.namespace_api.list(name="testrv").results[0]
        cls.namespace_api.delete(namespace.pulp_href)
        delete_orphans()
        del_user(cls.user_creator)
        del_user(cls.user_reader)
        del_user(cls.user_helpless)

    def test_repov_list(self):
        """
        Test that users can list repository versions if they have enough rights
        """
        self.assertEqual(self.repo_version_api.list(self.repository.pulp_href).count, 5)
        self.assertEqual(
            self.user_creator["repo_version_api"].list(self.repository.pulp_href).count, 5
        )
        self.assertEqual(
            self.user_reader["repo_version_api"].list(self.repository.pulp_href).count, 5
        )
        with self.assertRaises(ApiException):
            self.user_helpless["repo_version_api"].list(self.repository.pulp_href)

    def test_repov_read(self):
        """
        Test that users can read specific repository versions if they have enough rights
        """
        repository = self.pushrepository_api.read(self.repository.pulp_href)
        self.repo_version_api.read(repository.latest_version_href)
        self.user_creator["repo_version_api"].read(repository.latest_version_href)
        self.user_reader["repo_version_api"].read(repository.latest_version_href)
        with self.assertRaises(ApiException):
            self.user_helpless["repo_version_api"].read(repository.latest_version_href)


class PushCrossRepoBlobMountTestCase(PulpTestCase, rbac_base.BaseRegistryTest):
    """A test case for verifying the cross repository blob mount functionality.

    The test case also verifies whether different access scopes are evaluated properly or not. For
    instance, users who do not have permissions to pull and push content, they should not be able
    to trigger the cross repository blob mount procedure.
    """

    @classmethod
    def setUpClass(cls):
        """Initialize class-wide variables and create a new repository by pushing content to it."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.code_handler)
        cls.registry = cli.RegistryClient(cls.cfg)
        cls.registry.raise_if_unsupported(unittest.SkipTest, "Tests require podman/docker")

        cls.registry_name = urlparse(cls.cfg.get_base_url()).netloc

        admin_user, admin_password = cls.cfg.pulp_auth
        cls.user_admin = {"username": admin_user, "password": admin_password}

        api_client = gen_container_client()
        api_client.configuration.username = cls.user_admin["username"]
        api_client.configuration.password = cls.user_admin["password"]

        cls.distributions_api = DistributionsContainerApi(api_client)
        cls.pushrepository_api = RepositoriesContainerPushApi(api_client)
        cls.repo_version_api = RepositoriesContainerVersionsApi(api_client)
        cls.blobs_api = ContentBlobsApi(api_client)

        cls._pull(f"{REGISTRY_V2_REPO_PULP}:manifest_a")

        local_url = f"{cls.registry_name}/test-1:manifest_a"
        image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
        cls._push(image_path, local_url, cls.user_admin)

        repository = cls.pushrepository_api.list(name="test-1").results[0]
        cls.blobs = cls.blobs_api.list(repository_version=repository.latest_version_href).results
        cls.distribution = cls.distributions_api.list(name="test-1").results[0]

        cls.user_pull = gen_user(
            object_roles=[("container.containernamespace_consumer", cls.distribution.namespace)]
        )
        cls.user_push = gen_user(
            object_roles=[("container.containernamespace_collaborator", cls.distribution.namespace)]
        )
        cls.user_anon = gen_user()

    @classmethod
    def tearDownClass(cls):
        """Delete created users and a distribution that was created in the first stage."""
        monitor_task(cls.distributions_api.delete(cls.distribution.pulp_href).task)

        delete_orphans()
        del_user(cls.user_pull)
        del_user(cls.user_push)
        del_user(cls.user_anon)

    def tearDown(self):
        """Delete a newly created repository if exists."""
        distributions = self.distributions_api.list(name="test-2").results
        if distributions:
            monitor_task(self.distributions_api.delete(distributions[0].pulp_href).task)
            delete_orphans()

    def test_mount_blobs_as_admin(self):
        """Test if an admin user can trigger blob mounting successfully."""
        admin_basic_auth = (self.user_admin["username"], self.user_admin["password"])
        for i, blob in enumerate(self.blobs, 1):
            content_response, token_auth = self.mount_blob(blob, admin_basic_auth)
            assert content_response.status_code == 201
            assert content_response.text == ""

            blob_url = f"/v2/test-2/blobs/{blob.digest}"
            url = urljoin(self.cfg.get_base_url(), blob_url)
            content_response = self.client.head(url, auth=token_auth)
            assert content_response.status_code == 200

            repo_href = self.distributions_api.list(name="test-2").results[0].repository
            version_href = self.pushrepository_api.read(repo_href).latest_version_href
            assert f"{repo_href}versions/{i}/" == version_href

            added_blobs = self.blobs_api.list(repository_version_added=version_href).results
            assert len(added_blobs) == 1
            assert added_blobs[0].digest == blob.digest

    @unittest.skipIf(TOKEN_AUTH_DISABLED, "Only administrators can push content to the Registry.")
    def test_mount_blobs_as_user_pull(self):
        """Test if a user with pull permission, but not push permission, is not able to mount."""
        user_pull_basic_auth = self.user_pull["username"], self.user_pull["password"]
        for i, blob in enumerate(self.blobs, 1):
            content_response, _ = self.mount_blob(blob, user_pull_basic_auth)
            assert content_response.status_code == 401

    @unittest.skipIf(TOKEN_AUTH_DISABLED, "Only administrators can push content to the Registry.")
    def test_mount_blobs_as_user_push(self):
        """Test if a collaborator cannot mount content outside of his scope."""
        user_push_basic_auth = self.user_push["username"], self.user_push["password"]
        for i, blob in enumerate(self.blobs, 1):
            content_response, _ = self.mount_blob(blob, user_push_basic_auth)
            assert content_response.status_code == 401

    @unittest.skipIf(TOKEN_AUTH_DISABLED, "Only administrators can push content to the Registry.")
    def test_mount_blobs_as_user_anon(self):
        """Test if an anonymous user with no permissions is not able to mount."""
        user_anon_basic_auth = self.user_anon["username"], self.user_anon["password"]
        for i, blob in enumerate(self.blobs, 1):
            content_response, _ = self.mount_blob(blob, user_anon_basic_auth)
            assert content_response.status_code == 401

    def mount_blob(self, blob, basic_auth):
        """Try to mount the blob with the provided credentials."""
        mount_url = f"/v2/test-2/blobs/uploads/?from=test-1&mount={blob.digest}"
        url = urljoin(self.cfg.get_base_url(), mount_url)

        if TOKEN_AUTH_DISABLED:
            auth = basic_auth
        else:
            response = requests.post(url, auth=basic_auth)
            assert response.status_code == 401

            authenticate_header = response.headers["Www-Authenticate"]
            queries = AuthenticationHeaderQueries(authenticate_header)
            response = requests.get(
                queries.realm,
                params={
                    "service": queries.service,
                    "scope": [queries.scope, "repository:test-1:pull"],
                },
                auth=basic_auth,
            )
            response.raise_for_status()
            token = response.json()["token"]
            auth = BearerTokenAuth(token)

        return requests.post(url, auth=auth), auth

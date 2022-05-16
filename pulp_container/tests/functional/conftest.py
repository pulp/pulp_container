import pytest

from urllib.parse import urljoin, urlparse

import requests
from pulp_smash.cli import RegistryClient
from pulpcore.client.pulp_container import (
    ApiClient,
    PulpContainerNamespacesApi,
    RemotesContainerApi,
    RepositoriesContainerApi,
    RepositoriesContainerPushApi,
    RepositoriesContainerVersionsApi,
    RepositoriesContainerPushVersionsApi,
    DistributionsContainerApi,
    ContentTagsApi,
    ContentManifestsApi,
    ContentBlobsApi,
    ContentSignaturesApi,
)

from pulp_container.tests.functional.utils import (
    TOKEN_AUTH_DISABLED,
    AuthenticationHeaderQueries,
    BearerTokenAuth,
)


@pytest.fixture(scope="session")
def registry_client(pulp_cfg):
    """Fixture for a container registry client."""
    registry = RegistryClient(pulp_cfg)
    try:
        registry.raise_if_unsupported(ValueError, "Tests require podman/docker")
    except ValueError:
        pytest.Skip("Tests require podman/docker")

    return registry


@pytest.fixture()
def local_registry(request, _local_registry):
    """Local registry with authentication."""

    # This check only works, if the fixture is scoped to the test
    if request.node.get_closest_marker("parallel") is not None:
        raise pytest.UsageError("This test is not suitable to be marked parallel.")

    return _local_registry


@pytest.fixture(scope="session")
def _local_registry(pulp_cfg, bindings_cfg, registry_client):
    """Local registry with authentication. Session scoped."""

    registry_name = urlparse(pulp_cfg.get_base_url()).netloc

    class _LocalRegistry:
        @property
        def name(self):
            return registry_name

        @staticmethod
        def get_response(method, path, **kwargs):
            """Return a response while dealing with token authentication."""
            url = urljoin(pulp_cfg.get_base_url(), path)

            basic_auth = (bindings_cfg.username, bindings_cfg.password)
            if TOKEN_AUTH_DISABLED:
                auth = basic_auth
            else:
                extended_scope = kwargs.pop("scope", None)

                with pytest.raises(requests.HTTPError):
                    response = requests.request(method, url, auth=basic_auth, **kwargs)
                    response.raise_for_status()
                assert response.status_code == 401

                authenticate_header = response.headers["WWW-Authenticate"]
                queries = AuthenticationHeaderQueries(authenticate_header)

                scopes = [queries.scope]
                if extended_scope:
                    scopes.append(extended_scope)

                content_response = requests.get(
                    queries.realm,
                    params={"service": queries.service, "scope": scopes},
                    auth=basic_auth,
                )
                content_response.raise_for_status()
                token = content_response.json()["token"]
                auth = BearerTokenAuth(token)

            return requests.request(method, url, auth=auth, **kwargs), auth

        @staticmethod
        def _dispatch_command(*args):
            if bindings_cfg.username is not None:
                registry_client.login(
                    "-u", bindings_cfg.username, "-p", bindings_cfg.password, registry_name
                )
            else:
                registry_client.logout(registry_name)
            try:
                registry_client._dispatch_command(*args)
            finally:
                registry_client.logout(registry_name)

        @staticmethod
        def pull(image_path):
            if bindings_cfg.username is not None:
                registry_client.login(
                    "-u", bindings_cfg.username, "-p", bindings_cfg.password, registry_name
                )
            else:
                registry_client.logout(registry_name)
            try:
                registry_client.pull("/".join([registry_name, image_path]))
            finally:
                registry_client.logout(registry_name)

        @staticmethod
        def tag_and_push(image_path, local_url, *args):
            local_image_path = "/".join([registry_name, local_url])
            registry_client.tag(image_path, local_image_path)
            if bindings_cfg.username is not None:
                registry_client.login(
                    "-u", bindings_cfg.username, "-p", bindings_cfg.password, registry_name
                )
            else:
                registry_client.logout(registry_name)
            try:
                registry_client.push(local_image_path, *args)
            finally:
                # Untag local copy
                registry_client.rmi(local_image_path)
                registry_client.logout(registry_name)

        @staticmethod
        def inspect(local_url):
            local_image_path = "/".join([registry_name, local_url])
            return registry_client.inspect(local_image_path)

    return _LocalRegistry()


@pytest.fixture(scope="session")
def container_client(bindings_cfg):
    """Fixture for container_client."""
    return ApiClient(bindings_cfg)


@pytest.fixture(scope="session")
def container_namespace_api(container_client):
    """Container namespace API fixture."""
    return PulpContainerNamespacesApi(container_client)


@pytest.fixture(scope="session")
def container_remote_api(container_client):
    """Container remote API fixture."""
    return RemotesContainerApi(container_client)


@pytest.fixture(scope="session")
def container_repository_api(container_client):
    """Container repository API fixture."""
    return RepositoriesContainerApi(container_client)


@pytest.fixture(scope="session")
def container_repository_version_api(container_client):
    """Container repository version API fixture."""
    return RepositoriesContainerVersionsApi(container_client)


@pytest.fixture(scope="session")
def container_push_repository_api(container_client):
    """Container push repository API fixture."""
    return RepositoriesContainerPushApi(container_client)


@pytest.fixture(scope="session")
def container_push_repository_version_api(container_client):
    """Container repository version API fixture."""
    return RepositoriesContainerPushVersionsApi(container_client)


@pytest.fixture(scope="session")
def container_distribution_api(container_client):
    """Container distribution API fixture."""
    return DistributionsContainerApi(container_client)


@pytest.fixture(scope="session")
def container_tag_api(container_client):
    """Container tag API fixture."""
    return ContentTagsApi(container_client)


@pytest.fixture(scope="session")
def container_manifest_api(container_client):
    """Container manifest API fixture."""
    return ContentManifestsApi(container_client)


@pytest.fixture(scope="session")
def container_blob_api(container_client):
    """Container blob API fixture."""
    return ContentBlobsApi(container_client)


@pytest.fixture(scope="session")
def container_signature_api(container_client):
    """Container image signature API fixture."""
    return ContentSignaturesApi(container_client)

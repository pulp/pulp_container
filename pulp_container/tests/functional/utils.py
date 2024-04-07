"""Utilities for tests for the container plugin."""

import pytest
import requests

from requests.auth import AuthBase
from functools import partial
from unittest import SkipTest
from tempfile import NamedTemporaryFile
from uuid import uuid4

from pulp_smash import cli, config, selectors, utils
from pulp_smash.pulp3.bindings import monitor_task
from pulp_smash.pulp3.utils import (
    get_content,
)

from pulp_container.tests.functional.constants import (
    CONTAINER_CONTENT_NAME,
    CONTAINER_IMAGE_URL,
    PULP_HELLO_WORLD_REPO,
    REGISTRY_V2_FEED_URL,
)

from pulpcore.client.pulpcore import (
    ApiClient as CoreApiClient,
    ArtifactsApi,
    GroupsApi,
    GroupsUsersApi,
    UsersApi,
    UsersRolesApi,
)
from pulpcore.client.pulp_container import (
    ApiClient as ContainerApiClient,
    ContainerRepositorySyncURL,
    ContentBlobsApi,
    ContentManifestsApi,
    ContentTagsApi,
    RemotesContainerApi,
    DistributionsContainerApi,
    PulpContainerNamespacesApi,
    RepositoriesContainerApi,
    RepositoriesContainerPushApi,
    RepositoriesContainerVersionsApi,
)

cfg = config.get_config()
cli_client = cli.Client(cfg)
configuration = cfg.get_bindings_config()

core_client = CoreApiClient(configuration)
users_api = UsersApi(core_client)
users_roles_api = UsersRolesApi(core_client)


TOKEN_AUTH_DISABLED = utils.get_pulp_setting(cli_client, "TOKEN_AUTH_DISABLED")


def gen_user(model_roles=None, object_roles=None):
    """Create a user with a set of permissions in the pulp database."""
    if model_roles is None:
        model_roles = []

    if object_roles is None:
        object_roles = []

    user = {
        "username": utils.uuid4(),
        "password": utils.uuid4(),
    }
    new_user = users_api.create(user)
    user["pulp_href"] = new_user.pulp_href

    for role in model_roles:
        assign_role_to_user(user, role)
    for role, content_object in object_roles:
        assign_role_to_user(user, role, content_object)

    api_config = cfg.get_bindings_config()
    api_config.username = user["username"]
    api_config.password = user["password"]
    user["core_api_client"] = CoreApiClient(api_config)
    user["groups_api"] = GroupsApi(user["core_api_client"])
    user["group_users_api"] = GroupsUsersApi(user["core_api_client"])
    user["container_api_client"] = ContainerApiClient(api_config)
    user["namespace_api"] = PulpContainerNamespacesApi(user["container_api_client"])
    user["distribution_api"] = DistributionsContainerApi(user["container_api_client"])
    user["remote_api"] = RemotesContainerApi(user["container_api_client"])
    user["repository_api"] = RepositoriesContainerApi(user["container_api_client"])
    user["pushrepository_api"] = RepositoriesContainerPushApi(user["container_api_client"])
    user["repo_version_api"] = RepositoriesContainerVersionsApi(user["container_api_client"])
    user["tags_api"] = ContentTagsApi(user["container_api_client"])
    user["manifests_api"] = ContentManifestsApi(user["container_api_client"])
    user["blobs_api"] = ContentBlobsApi(user["container_api_client"])
    return user


def del_user(user):
    """Delete a user from the pulp database."""
    users_api.delete(user["pulp_href"])


def assign_role_to_user(user, role, content_object=None):
    """Assign a role to a user with an optional object."""
    users_roles_api.create(
        auth_user_href=user["pulp_href"], user_role={"role": role, "content_object": content_object}
    )


def gen_container_client():
    """Return an OBJECT for container client."""
    return ContainerApiClient(configuration)


def gen_repo(**kwargs):
    """Return a semi-random dict for use in creating a Repository."""
    data = {"name": str(uuid4())}
    data.update(kwargs)
    return data


def gen_remote(url, **kwargs):
    """Return a semi-random dict for use in creating a Remote.
    :param url: The URL of an external content source.
    """
    data = {"name": str(uuid4()), "url": url}
    data.update(kwargs)
    return data


def gen_container_remote(url=REGISTRY_V2_FEED_URL, **kwargs):
    """Return a semi-random dict for use in creating a container Remote.

    :param url: The URL of an external content source.
    """
    return gen_remote(
        url, upstream_name=kwargs.pop("upstream_name", PULP_HELLO_WORLD_REPO), **kwargs
    )


def get_blobsums_from_remote_registry(upstream_name=PULP_HELLO_WORLD_REPO):
    """Get remote blobsum list from a remote registry."""
    token_server_response = requests.get(
        f"{REGISTRY_V2_FEED_URL}/token?service=ghcr.io&scope=repository:{upstream_name}:pull"
    )
    token_server_response.raise_for_status()
    token = token_server_response.json()["token"]

    s = requests.Session()
    s.headers.update({"Authorization": "Bearer " + token})

    # the tag 'latest' references a manifest list
    manifest_url = f"{REGISTRY_V2_FEED_URL}/v2/{upstream_name}/manifests/latest"
    response = s.get(manifest_url)
    response.raise_for_status()

    checksums = []
    for manifest in response.json()["manifests"]:
        manifest_url = f"{REGISTRY_V2_FEED_URL}/v2/{upstream_name}/manifests/{manifest['digest']}"
        response = s.get(manifest_url)
        response.raise_for_status()

        for layer in response.json()["layers"]:
            checksums.append(layer["digest"])

    return checksums


def get_container_image_paths(repo, version_href=None):
    """Return the relative path of content units present in a container repository.

    :param repo: A dict of information about the repository.
    :param version_href: The repository version to read.
    :returns: A list with the paths of units present in a given repository.
    """
    return [
        content_unit["_artifact"]
        for content_unit in get_content(repo, version_href)[CONTAINER_CONTENT_NAME]
    ]


def populate_pulp(url=REGISTRY_V2_FEED_URL):
    """Add container contents to Pulp.

    :param url: The container repository URL. Defaults to
        :data:`pulp_container.tests.functional.constants.REGISTRY_V2_FEED_URL`
    :returns: A dictionary of created resources.
    """
    container_client = ContainerApiClient(configuration)
    remotes_api = RemotesContainerApi(container_client)
    repositories_api = RepositoriesContainerApi(container_client)

    container_remote = remotes_api.create(gen_container_remote(url))
    sync_data = ContainerRepositorySyncURL(remote=container_remote.pulp_href)
    container_repository = repositories_api.create(gen_repo())
    sync_response = repositories_api.sync(container_repository.pulp_href, sync_data)

    return monitor_task(sync_response.task).created_resources


class BearerTokenAuth(AuthBase):
    """A subclass for building a JWT Authorization header out of a provided token."""

    def __init__(self, token):
        """Store a Bearer token that is going to be used in the request object."""
        self.token = token

    def __call__(self, r):
        """Attaches a Bearer token authentication to the given request object."""
        r.headers["Authorization"] = "Bearer {}".format(self.token)
        return r


class AuthenticationHeaderQueries:
    """A data class to store header queries located in the Www-Authenticate header."""

    def __init__(self, authenticate_header):
        """
        Extract service and realm from the header.

        The scope is not provided by the token server because we are accessing the endpoint from
        the root.
        """
        self.scopes = []

        if not authenticate_header.lower().startswith("bearer "):
            raise Exception(f"Authentication header has wrong format.\n{authenticate_header}")
        for item in authenticate_header[7:].split(","):
            key, value = item.split("=")
            if key == "scope":
                self.scopes.append(value.strip('"'))
            else:
                setattr(self, key, value.strip('"'))


skip_if = partial(selectors.skip_if, exc=SkipTest)
"""The ``@skip_if`` decorator, customized for unittest.

:func:`pulp_smash.selectors.skip_if` is test runner agnostic. This function is
identical, except that ``exc`` has been set to ``unittest.SkipTest``.
"""


def gen_artifact(url=CONTAINER_IMAGE_URL):
    """Create an artifact."""
    response = requests.get(url)
    with NamedTemporaryFile() as temp_file:
        temp_file.write(response.content)
        artifact = ArtifactsApi(core_client).create(file=temp_file.name)
        return artifact.to_dict()


def get_auth_for_url(registry_endpoint_url, auth=None):
    """Return authentication details based on the the status of token authentication."""
    if TOKEN_AUTH_DISABLED:
        auth = ()
    else:
        with pytest.raises(requests.HTTPError):
            response = requests.get(registry_endpoint_url)
            response.raise_for_status()
        assert response.status_code == 401

        authenticate_header = response.headers["WWW-Authenticate"]
        queries = AuthenticationHeaderQueries(authenticate_header)
        content_response = requests.get(
            queries.realm, params={"service": queries.service, "scope": queries.scopes}, auth=auth
        )
        content_response.raise_for_status()
        token = content_response.json()["token"]
        auth = BearerTokenAuth(token)

    return auth

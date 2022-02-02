# coding=utf-8
"""Utilities for tests for the container plugin."""
import requests

from requests.auth import AuthBase
from functools import partial
from unittest import SkipTest
from tempfile import NamedTemporaryFile

from pulp_smash import cli, config, selectors, utils
from pulp_smash.pulp3.bindings import monitor_task
from pulp_smash.pulp3.utils import (
    gen_remote,
    gen_repo,
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
    TasksApi,
)
from pulpcore.client.pulp_container import (
    ApiClient as ContainerApiClient,
    ContentBlobsApi,
    ContentManifestsApi,
    ContentTagsApi,
    RemotesContainerApi,
    DistributionsContainerApi,
    RepositoriesContainerApi,
    RepositoriesContainerPushApi,
    RepositoriesContainerVersionsApi,
    RepositorySyncURL,
)

cfg = config.get_config()
cli_client = cli.Client(cfg)
configuration = cfg.get_bindings_config()


TOKEN_AUTH_DISABLED = utils.get_pulp_setting(cli_client, "TOKEN_AUTH_DISABLED")


CREATE_USER_CMD = [
    "from django.contrib.auth import get_user_model",
    "from django.urls import resolve",
    "from guardian.shortcuts import assign_perm",
    "",
    "user = get_user_model().objects.create(username='{username}')",
    "user.set_password('{password}')",
    "user.save()",
    "",
    "for permission in {model_permissions!r}:",
    "    assign_perm(permission, user)",
    "",
    "for permission, obj_url in {object_permissions!r}:",
    "    func, _, kwargs = resolve(obj_url)",
    "    obj = func.cls.queryset.get(pk=kwargs['pk'])",
    "    assign_perm(permission, user, obj)",
]


DELETE_USER_CMD = [
    "from django.contrib.auth import get_user_model",
    "get_user_model().objects.get(username='{username}').delete()",
]


def gen_user(model_permissions=None, object_permissions=None):
    """Create a user with a set of permissions in the pulp database."""
    if model_permissions is None:
        model_permissions = []

    if object_permissions is None:
        object_permissions = []

    user = {
        "username": utils.uuid4(),
        "password": utils.uuid4(),
        "model_permissions": model_permissions,
        "object_permissions": object_permissions,
    }
    utils.execute_pulpcore_python(
        cli_client,
        "\n".join(CREATE_USER_CMD).format(**user),
    )

    api_config = cfg.get_bindings_config()
    api_config.username = user["username"]
    api_config.password = user["password"]
    user["core_api_client"] = CoreApiClient(api_config)
    user["groups_api"] = GroupsApi(user["core_api_client"])
    user["group_users_api"] = GroupsUsersApi(user["core_api_client"])
    user["api_client"] = ContainerApiClient(api_config)
    user["distribution_api"] = DistributionsContainerApi(user["api_client"])
    user["remote_api"] = RemotesContainerApi(user["api_client"])
    user["repository_api"] = RepositoriesContainerApi(user["api_client"])
    user["pushrepository_api"] = RepositoriesContainerPushApi(user["api_client"])
    user["repo_version_api"] = RepositoriesContainerVersionsApi(user["api_client"])
    user["tags_api"] = ContentTagsApi(user["api_client"])
    user["manifests_api"] = ContentManifestsApi(user["api_client"])
    user["blobs_api"] = ContentBlobsApi(user["api_client"])
    return user


def del_user(user):
    """Delete a user from the pulp database."""
    utils.execute_pulpcore_python(
        cli_client,
        "\n".join(DELETE_USER_CMD).format(**user),
    )


def add_user_to_distribution_group(user, distribution, group_type, as_user):
    """Add the user to either owner, collaborator, or consumer group of a distribution."""
    distribution_pk = distribution.pulp_href.split("/")[-2]
    collaborator_group = (
        as_user["groups_api"]
        .list(name="container.distribution.{}.{}".format(group_type, distribution_pk))
        .results[0]
    )
    as_user["group_users_api"].create(collaborator_group.pulp_href, {"username": user["username"]})


def add_user_to_namespace_group(user, namespace_name, group_type, as_user):
    """Add the user to either owner, collaborator, or consumer group of a namespace."""
    namespace_collaborator_group = (
        as_user["groups_api"]
        .list(name="container.namespace.{}.{}".format(group_type, namespace_name))
        .results[0]
    )
    as_user["group_users_api"].create(
        namespace_collaborator_group.pulp_href,
        {"username": user["username"]},
    )


def gen_container_client():
    """Return an OBJECT for container client."""
    return ContainerApiClient(configuration)


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


def gen_container_content_attrs(artifact):
    """Generate a dict with content unit attributes.

    :param artifact: An artifact.
    :returns: A semi-random dict for use in creating a content unit.
    """
    # FIXME: Add content specific metadata here.
    return {"_artifact": artifact.pulp_href}


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
    sync_data = RepositorySyncURL(remote=container_remote.pulp_href)
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
        if not authenticate_header.lower().startswith("bearer "):
            raise Exception(f"Authentication header has wrong format.\n{authenticate_header}")
        for item in authenticate_header[7:].split(","):
            key, value = item.split("=")
            setattr(self, key, value.strip('"'))


skip_if = partial(selectors.skip_if, exc=SkipTest)
"""The ``@skip_if`` decorator, customized for unittest.

:func:`pulp_smash.selectors.skip_if` is test runner agnostic. This function is
identical, except that ``exc`` has been set to ``unittest.SkipTest``.
"""

core_client = CoreApiClient(configuration)
tasks = TasksApi(core_client)


def gen_artifact(url=CONTAINER_IMAGE_URL):
    """Create an artifact."""
    response = requests.get(url)
    with NamedTemporaryFile() as temp_file:
        temp_file.write(response.content)
        artifact = ArtifactsApi(core_client).create(file=temp_file.name)
        return artifact.to_dict()

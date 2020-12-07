# coding=utf-8
"""Utilities for tests for the container plugin."""
import requests

from requests.auth import AuthBase
from functools import partial
from unittest import SkipTest
from tempfile import NamedTemporaryFile

from pulp_smash import selectors, config
from pulp_smash.pulp3.bindings import monitor_task
from pulp_smash.pulp3.utils import (
    gen_remote,
    gen_repo,
    get_content,
)

from pulp_container.tests.functional.constants import (
    CONTAINER_CONTENT_NAME,
    CONTAINER_IMAGE_URL,
    REPO_UPSTREAM_NAME,
    REGISTRY_V2_FEED_URL,
)

from pulpcore.client.pulpcore import (
    ApiClient as CoreApiClient,
    ArtifactsApi,
    TasksApi,
)
from pulpcore.client.pulp_container import (
    ApiClient as ContainerApiClient,
    RemotesContainerApi,
    RepositoriesContainerApi,
    RepositorySyncURL,
)

cfg = config.get_config()
configuration = cfg.get_bindings_config()


def gen_container_client():
    """Return an OBJECT for container client."""
    return ContainerApiClient(configuration)


def gen_container_remote(url=REGISTRY_V2_FEED_URL, **kwargs):
    """Return a semi-random dict for use in creating a container Remote.

    :param url: The URL of an external content source.
    """
    return gen_remote(url, upstream_name=kwargs.pop("upstream_name", REPO_UPSTREAM_NAME), **kwargs)


def get_docker_hub_remote_blobsums(upstream_name=REPO_UPSTREAM_NAME):
    """Get remote blobsum list from dockerhub registry."""
    token_url = (
        "https://auth.docker.io/token"
        "?service=registry.docker.io"
        "&scope=repository:library/{0}:pull"
    ).format(upstream_name)
    token_response = requests.get(token_url)
    token_response.raise_for_status()
    token = token_response.json()["token"]

    blob_url = ("{0}/v2/library/{1}/manifests/latest").format(REGISTRY_V2_FEED_URL, upstream_name)
    response = requests.get(blob_url, headers={"Authorization": "Bearer " + token})
    response.raise_for_status()
    return response.json()["fsLayers"]


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

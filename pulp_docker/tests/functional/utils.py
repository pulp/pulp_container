# coding=utf-8
"""Utilities for tests for the docker plugin."""
import requests
from functools import partial
from unittest import SkipTest

from pulp_smash import api, selectors
from pulp_smash.pulp3.utils import (
    gen_remote,
    gen_repo,
    get_content,
    require_pulp_3,
    require_pulp_plugins,
    sync
)

from pulp_docker.tests.functional.constants import (
    DOCKER_CONTENT_NAME,
    DOCKER_CONTENT_PATH,
    DOCKER_REMOTE_PATH,
    DOCKER_REPO_PATH,
    DOCKER_UPSTREAM_NAME,
    DOCKER_V2_FEED_URL,
)


def set_up_module():
    """Skip tests Pulp 3 isn't under test or if pulp_docker isn't installed."""
    require_pulp_3(SkipTest)
    require_pulp_plugins({'pulp_docker'}, SkipTest)


def gen_docker_remote(**kwargs):
    """Generate dict with common remote properties."""
    return gen_remote(
        kwargs.pop('url', DOCKER_V2_FEED_URL),
        upstream_name=kwargs.pop('upstream_name', DOCKER_UPSTREAM_NAME),
        **kwargs
    )


def get_docker_hub_remote_blobsums(upstream_name=DOCKER_UPSTREAM_NAME):
    """Get remote blobsum list from dockerhub registry."""
    token_url = (
        'https://auth.docker.io/token'
        '?service=registry.docker.io'
        '&scope=repository:library/{0}:pull'
    ).format(upstream_name)
    token_response = requests.get(token_url)
    token_response.raise_for_status()
    token = token_response.json()['token']

    blob_url = (
        '{0}/v2/library/{1}/manifests/latest'
    ).format(DOCKER_V2_FEED_URL, upstream_name)
    response = requests.get(
        blob_url,
        headers={'Authorization': 'Bearer ' + token}
    )
    response.raise_for_status()
    return response.json()['fsLayers']


def get_docker_image_paths(repo, version_href=None):
    """Return the relative path of content units present in a file repository.

    :param repo: A dict of information about the repository.
    :param version_href: The repository version to read.
    :returns: A list with the paths of units present in a given repository.
    """
    return [
        content_unit['_artifact']
        for content_unit
        in get_content(repo, version_href)[DOCKER_CONTENT_NAME]
    ]


def gen_docker_image_attrs(artifact):
    """Generate a dict with content unit attributes.

    :param: artifact: A dict of info about the artifact.
    :returns: A semi-random dict for use in creating a content unit.
    """
    # FIXME: Add content specific metadata here.
    return {'_artifact': artifact['pulp_href']}


def populate_pulp(cfg, url=DOCKER_V2_FEED_URL):
    """Add docker contents to Pulp.

    :param pulp_smash.config.PulpSmashConfig: Information about a Pulp application.
    :param url: The docker repository URL. Defaults to
        :data:`pulp_smash.constants.DOCKER_FIXTURE_URL`
    :returns: A list of dicts, where each dict describes one file content in Pulp.
    """
    client = api.Client(cfg, api.json_handler)
    remote = {}
    repo = {}
    try:
        remote.update(
            client.post(
                DOCKER_REMOTE_PATH,
                gen_remote(url, upstream_name=DOCKER_UPSTREAM_NAME)

            )
        )
        repo.update(client.post(DOCKER_REPO_PATH, gen_repo()))
        sync(cfg, remote, repo)
    finally:
        if remote:
            client.delete(remote['pulp_href'])
        if repo:
            client.delete(repo['pulp_href'])
    return client.get(DOCKER_CONTENT_PATH)['results']


skip_if = partial(selectors.skip_if, exc=SkipTest)
"""The ``@skip_if`` decorator, customized for unittest.

:func:`pulp_smash.selectors.skip_if` is test runner agnostic. This function is
identical, except that ``exc`` has been set to ``unittest.SkipTest``.
"""

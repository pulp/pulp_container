# coding=utf-8
from urllib.parse import urljoin

from pulp_smash.constants import PULP_FIXTURES_BASE_URL
from pulp_smash.pulp3.constants import (
    BASE_PATH,
    BASE_DISTRIBUTION_PATH,
    BASE_REMOTE_PATH,
    BASE_REPO_PATH,
    BASE_CONTENT_PATH
)

DOCKER_MANIFEST_PATH = urljoin(BASE_CONTENT_PATH, 'docker/manifests/')

DOCKER_TAG_PATH = urljoin(BASE_CONTENT_PATH, 'docker/tags/')

DOCKER_BLOB_PATH = urljoin(BASE_CONTENT_PATH, 'docker/blobs/')

DOCKER_CONTENT_PATH = urljoin(BASE_CONTENT_PATH, 'docker/unit/')

DOCKER_TAGGING_PATH = urljoin(BASE_PATH, 'docker/tag/')

DOCKER_UNTAGGING_PATH = urljoin(BASE_PATH, 'docker/untag/')

DOCKER_TAG_COPY_PATH = urljoin(BASE_PATH, 'docker/tags/copy/')

DOCKER_MANIFEST_COPY_PATH = urljoin(BASE_PATH, 'docker/manifests/copy/')

DOCKER_CONTENT_NAME = 'docker.blob'

DOCKER_DISTRIBUTION_PATH = urljoin(BASE_DISTRIBUTION_PATH, 'docker/docker/')

DOCKER_REMOTE_PATH = urljoin(BASE_REMOTE_PATH, 'docker/docker/')

DOCKER_REPO_PATH = urljoin(BASE_REPO_PATH, 'docker/docker/')

DOCKER_RECURSIVE_ADD_PATH = urljoin(BASE_PATH, 'docker/recursive-add/')

DOCKER_RECURSIVE_REMOVE_PATH = urljoin(BASE_PATH, 'docker/recursive-remove/')

DOCKER_IMAGE_URL = urljoin(PULP_FIXTURES_BASE_URL, 'docker/busybox:latest.tar')
"""The URL to a Docker image as created by ``docker save``."""

# hello-world is the smalest docker image available on docker hub 1.84kB
DOCKER_UPSTREAM_NAME = 'hello-world'
"""The name of a Docker repository.

This repository has several desireable properties:

* It is available via both :data:`DOCKER_V1_FEED_URL` and
  :data:`DOCKER_V2_FEED_URL`.
* It has a manifest list, where one entry has an architecture of amd64 and an
  os of linux. (The "latest" tag offers this.)
* It is relatively small.

This repository also has several shortcomings:

* This repository isn't an official repository. It's less trustworthy, and may
  be more likely to change with little or no notice.
* It doesn't have a manifest list where no list entries have an architecture of
  amd64 and an os of linux. (The "arm32v7" tag provides schema v1 content.)

One can get a high-level view of the content in this repository by executing:

.. code-block:: sh

    curl --location --silent \
    https://registry.hub.docker.com/v2/repositories/$this_constant/tags \
    | python -m json.tool
"""

DOCKER_UPSTREAM_TAG = ":linux"
"""Alternative tag for the DOCKER_UPSTREAM_NAME image."""

DOCKER_V1_FEED_URL = 'https://index.docker.io'
"""The URL to a V1 Docker registry.

This URL can be used as the "feed" property of a Pulp Docker registry.
"""

DOCKER_V2_FEED_URL = 'https://registry-1.docker.io'
"""The URL to a V2 Docker registry.

This URL can be used as the "feed" property of a Pulp Docker registry.
"""

DOCKERHUB_PULP_FIXTURE_1 = 'pulp/test-fixture-1'

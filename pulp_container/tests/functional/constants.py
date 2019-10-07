# coding=utf-8
from urllib.parse import urljoin

from pulp_smash.constants import PULP_FIXTURES_BASE_URL
from pulp_smash.pulp3.constants import (
    BASE_PATH,
    BASE_DISTRIBUTION_PATH,
    BASE_REMOTE_PATH,
    CONTENT_PATH
)

CONTAINER_MANIFEST_PATH = urljoin(CONTENT_PATH, 'container/manifests/')

CONTAINER_TAG_PATH = urljoin(CONTENT_PATH, 'container/tags/')

CONTAINER_BLOB_PATH = urljoin(CONTENT_PATH, 'container/blobs/')

CONTAINER_CONTENT_PATH = urljoin(CONTENT_PATH, 'container/unit/')

CONTAINER_TAGGING_PATH = urljoin(BASE_PATH, 'container/tag/')

CONTAINER_UNTAGGING_PATH = urljoin(BASE_PATH, 'container/untag/')

CONTAINER_TAG_COPY_PATH = urljoin(BASE_PATH, 'container/tags/copy/')

CONTAINER_MANIFEST_COPY_PATH = urljoin(BASE_PATH, 'container/manifests/copy/')

CONTAINER_CONTENT_NAME = 'container.blob'

CONTAINER_DISTRIBUTION_PATH = urljoin(BASE_DISTRIBUTION_PATH, 'container/container/')

CONTAINER_REMOTE_PATH = urljoin(BASE_REMOTE_PATH, 'container/container/')

CONTAINER_RECURSIVE_ADD_PATH = urljoin(BASE_PATH, 'container/recursive-add/')

CONTAINER_RECURSIVE_REMOVE_PATH = urljoin(BASE_PATH, 'container/recursive-remove/')

CONTAINER_IMAGE_URL = urljoin(PULP_FIXTURES_BASE_URL, 'container/busybox:latest.tar')
"""The URL to a Container image as created by ``docker save``."""

# hello-world is the smalest container image available on docker hub 1.84kB
REPO_UPSTREAM_NAME = 'hello-world'
"""The name of a Container repository.

This repository has several desireable properties:

* It is available via both :data:`REGISTRY_V1_FEED_URL` and
  :data:`REGISTRY_V2_FEED_URL`.
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

REPO_UPSTREAM_TAG = ":linux"
"""Alternative tag for the REPO_UPSTREAM_NAME image."""

REGISTRY_V1_FEED_URL = 'https://index.docker.io'
"""The URL to a V1 Docker registry.

This URL can be used as the "feed" property of a Pulp Container registry.
"""

REGISTRY_V2_FEED_URL = 'https://registry-1.docker.io'
"""The URL to a V2 Docker registry.

This URL can be used as the "feed" property of a Pulp Container registry.
"""

DOCKERHUB_PULP_FIXTURE_1 = 'pulp/test-fixture-1'

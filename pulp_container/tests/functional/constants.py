from urllib.parse import urljoin

from pulp_smash.constants import PULP_FIXTURES_BASE_URL
from pulp_smash.pulp3.constants import (
    BASE_DISTRIBUTION_PATH,
    BASE_REMOTE_PATH,
    BASE_REPO_PATH,
    BASE_CONTENT_PATH,
)

CONTAINER_MANIFEST_PATH = urljoin(BASE_CONTENT_PATH, "container/manifests/")

CONTAINER_TAG_PATH = urljoin(BASE_CONTENT_PATH, "container/tags/")

CONTAINER_BLOB_PATH = urljoin(BASE_CONTENT_PATH, "container/blobs/")

CONTAINER_CONTENT_NAME = "container.blob"

CONTAINER_DISTRIBUTION_PATH = urljoin(BASE_DISTRIBUTION_PATH, "container/container/")

CONTAINER_REPO_PATH = urljoin(BASE_REPO_PATH, "container/container/")

CONTAINER_REMOTE_PATH = urljoin(BASE_REMOTE_PATH, "container/container/")

CONTAINER_IMAGE_URL = urljoin(PULP_FIXTURES_BASE_URL, "container/busybox:latest.tar")
"""The URL to a Container image as created by ``docker save``."""

# GH Packages registry
REGISTRY_V2 = "ghcr.io"
REGISTRY_V2_FEED_URL = "https://ghcr.io"

# a repository having the size of 1.84kB
PULP_HELLO_WORLD_REPO = "pulp/hello-world"
PULP_HELLO_WORLD_LINUX_AMD64_DIGEST = (
    "sha256:239de6dd745ed1a211123322865b4c342c706e7c1e01644a1bbefe8f8846c5ff"
)

# a repository containing 4 manifest lists and 5 manifests
PULP_FIXTURE_1 = "pulp/test-fixture-1"
PULP_FIXTURE_1_MANIFEST_A_DIGEST = (
    "sha256:d8fbbbf3fec1857c32c110292a9decf9744f9f97d7247019ae4776c241395221"
)

# a dummy repository containing two manifests (index and image) with an arbitrary bootc label
PULP_LABELED_FIXTURE = "pulp/bootc-labeled"

# an alternative tag for the PULP_HELLO_WORLD image referencing a manifest list
PULP_HELLO_WORLD_LINUX_TAG = ":linux"

REGISTRY_V2_REPO_PULP = f"{REGISTRY_V2}/{PULP_FIXTURE_1}"
REGISTRY_V2_REPO_HELLO_WORLD = f"{REGISTRY_V2}/{PULP_HELLO_WORLD_REPO}"

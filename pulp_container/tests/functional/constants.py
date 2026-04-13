CONTAINER_CONTENT_NAME = "container.blob"

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

# a repository containing cosign companion tags
PULP_COSIGN_COMPANION_TAGS = "pulp/cosign-tags"
# It contains 4 normal tags:
# manifest_a, manifest_b, manifest_c, manifest_d
# and 5 cosign companion tags:
# 2 for manifest_a: sha256-<digest>.sig (v2: 1 signature), sha256-<digest>.att (v2: 1 attestation)
# 2 for manifest_b: sha256-<digest>.sig (v2: 2 signatures), sha256-<digest> (v3: 2 signatures)
# 1 for manifest_c: sha256-<digest> (v3: 1 signature, 1 attestation)
# V2 signatures are stored in one manifest with each signature in a separate layer
# V3 signatures are collected in one manifest list with each signature getting its own manifest
# Repo total contains 2 manifest lists and 11 manifests

PULP_COSIGN_TAGS_MANIFEST_A_DIGEST = PULP_FIXTURE_1_MANIFEST_A_DIGEST
PULP_COSIGN_TAGS_MANIFEST_B_DIGEST = (
    "sha256:f8634bb68dccf0dc2a3113933a67f91dc10c4ac17dee90988cb6bc4ae55cf802"
)
PULP_COSIGN_TAGS_MANIFEST_C_DIGEST = (
    "sha256:6489ee892f64e59755435ee53f7d10cce5588a7788b4b2ae4a510a8bbc92704d"
)
PULP_COSIGN_TAGS_MANIFEST_D_DIGEST = (
    "sha256:badde852ff2ee4daeff0cf1c2b1e9c01a193ca6e93e0fce8acce8a7d6a4ade06"
)

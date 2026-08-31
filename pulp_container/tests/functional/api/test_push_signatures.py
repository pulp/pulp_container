"""Tests that verify that an image signature can be pushed to Pulp."""

import base64
import subprocess

import pytest

from pulp_container.constants import SIGNATURE_TYPE
from pulp_container.tests.functional.conftest import verify_inline_signature
from pulp_container.tests.functional.constants import REGISTRY_V2_REPO_PULP


def _podman_supports_sq_signing():
    """Return True if the local podman build supports --sign-by-sq-fingerprint."""
    result = subprocess.run(
        ("podman", "push", "--help"),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return "--sign-by-sq-fingerprint" in result.stdout.decode()


@pytest.fixture
def signed_distribution(
    signing_key_home,
    registry_client,
    local_registry,
    container_distribution_api,
    container_namespace_api,
    add_to_cleanup,
    full_path,
):
    """Push an image signed with a Sequoia key (twice, for two distinct signatures).

    Parameterized (via `signing_key_home`) over a key that signs with its primary key and
    one that signs with a dedicated subkey.
    """
    if registry_client.name != "podman":
        pytest.skip("This test requires podman to sign pulled content", allow_module_level=True)
    if not _podman_supports_sq_signing():
        pytest.skip("This podman build does not support --sign-by-sq-fingerprint")

    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    registry_client.pull(image_path)

    # Point the Sequoia integration at the home holding our imported key.
    sign_args = ("--sign-by-sq-fingerprint", signing_key_home.fingerprint)
    with registry_client.set_env(SEQUOIA_HOME=str(signing_key_home.home)):
        local_registry.tag_and_push(image_path, full_path("test-1:manifest_a"), *sign_args)
        # push a second time to produce a distinct signature (timestamp)
        local_registry.tag_and_push(image_path, full_path("test-1:manifest_a"), *sign_args)

    distribution = container_distribution_api.list(name="test-1").results[0]
    # Clean up the namespace, which cascades to the distribution and the push repository.
    add_to_cleanup(container_namespace_api, distribution.namespace)

    return distribution


def test_assert_signed_image(
    signing_key_home,
    local_registry,
    container_repository_api,
    container_manifest_api,
    container_signature_api,
    signed_distribution,
    full_path,
):
    """Test whether an admin user can fetch a signature from the Pulp Registry.

    Runs against both primary-key and subkey signing.
    """
    distribution = signed_distribution
    fingerprint = signing_key_home.signing_fingerprint
    keyid = signing_key_home.signing_keyid

    repository = container_repository_api.read(distribution.repository)
    manifest = container_manifest_api.list(
        repository_version=repository.latest_version_href
    ).results[0]

    signature = container_signature_api.list(
        repository_version=repository.latest_version_href
    ).results[0]

    assert manifest.digest in signature.name
    assert signature.signed_manifest == manifest.pulp_href
    assert signature.key_id == keyid
    assert signature.fingerprint == fingerprint

    path = f"/extensions/v2/{full_path(distribution)}/signatures/{manifest.digest}"
    response, _ = local_registry.get_response("GET", path)

    signatures = response.json()["signatures"]

    assert len(signatures) == 2

    timestamps = []
    for s in signatures:
        raw_s = base64.b64decode(s["content"])
        sig_fingerprint, sig_key_id, json_s = verify_inline_signature(
            signing_key_home.public_key, raw_s
        )

        assert sig_key_id == keyid
        assert sig_fingerprint == fingerprint

        image_path = json_s["critical"]["identity"]["docker-reference"]
        assert image_path == f"{local_registry.name}/{full_path(distribution)}:manifest_a"

        s_type = json_s["critical"]["type"]
        assert s_type == SIGNATURE_TYPE.ATOMIC_FULL

        referenced_manifest = json_s["critical"]["image"]["docker-manifest-digest"]
        assert referenced_manifest == manifest.digest

        timestamps.append(json_s["optional"]["timestamp"])

    assert timestamps[0] != timestamps[1]

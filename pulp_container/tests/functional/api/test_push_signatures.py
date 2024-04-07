"""Tests that verify that an image signature can be pushed to Pulp."""

import base64
import json
import pytest

from pulp_container.tests.functional.constants import REGISTRY_V2_REPO_PULP
from pulp_container.constants import SIGNATURE_TYPE


@pytest.fixture
def distribution(
    registry_client,
    local_registry,
    container_distribution_api,
    signing_gpg_metadata,
    add_to_cleanup,
):
    """Return a distribution created after pushing a signed content to the Pulp Registry."""
    if registry_client.name != "podman":
        pytest.skip("This test requires podman to sign pulled content", allow_module_level=True)

    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    registry_client.pull(image_path)

    gpg, fingerprint, keyid = signing_gpg_metadata

    with registry_client.set_env(GNUPGHOME=str(gpg.gnupghome)):
        local_registry.tag_and_push(image_path, "test-1:manifest_a", "--sign-by", keyid)

        # push the same image for the second time with a different signature (timestamp)
        local_registry.tag_and_push(image_path, "test-1:manifest_a", "--sign-by", keyid)

    distribution = container_distribution_api.list(name="test-1").results[0]
    add_to_cleanup(container_distribution_api, distribution.pulp_href)

    return distribution


def test_assert_signed_image(
    local_registry,
    container_push_repository_api,
    container_manifest_api,
    container_signature_api,
    signing_gpg_metadata,
    distribution,
):
    """Test whether an admin user can fetch a signature from the Pulp Registry."""
    gpg, fingerprint, keyid = signing_gpg_metadata

    repository = container_push_repository_api.read(distribution.repository)
    manifest = container_manifest_api.list(
        repository_version=repository.latest_version_href
    ).results[0]

    signature = container_signature_api.list(
        repository_version=repository.latest_version_href
    ).results[0]

    assert manifest.digest in signature.name
    assert signature.signed_manifest == manifest.pulp_href
    assert signature.key_id == keyid

    path = f"/extensions/v2/test-1/signatures/{manifest.digest}"
    response, _ = local_registry.get_response("GET", path)

    signatures = response.json()["signatures"]

    assert len(signatures) == 2

    timestamps = []
    for s in signatures:
        raw_s = base64.b64decode(s["content"])
        decrypted = gpg.decrypt(raw_s)

        assert decrypted.key_id == keyid
        assert decrypted.status == "signature valid"

        json_s = json.loads(decrypted.data)

        image_path = json_s["critical"]["identity"]["docker-reference"]
        assert image_path == f"{local_registry.name}/test-1:manifest_a"

        s_type = json_s["critical"]["type"]
        assert s_type == SIGNATURE_TYPE.ATOMIC_FULL

        referenced_manifest = json_s["critical"]["image"]["docker-manifest-digest"]
        assert referenced_manifest == manifest.digest

        timestamps.append(json_s["optional"]["timestamp"])

    assert timestamps[0] != timestamps[1]

import pytest

from pulpcore.pytest_plugin import create_signing_service, remove_signing_service

from pulp_container.constants import SIGNATURE_TYPE
from pulp_container.tests.functional.constants import REGISTRY_V2_REPO_PULP

MANIFEST_TAG = "manifest_a"

# Builds an atomic container signature payload for the passed manifest and signs
# it with a Sequoia (sq) key, emitting an inline-signed binary OpenPGP message.
# See https://github.com/pulp/pulp_container/issues/2280.
SIGNING_SCRIPT_STRING = """#!/usr/bin/env bash

set -e

MANIFEST_PATH=$1
FINGERPRINT="$PULP_SIGNING_KEY_FINGERPRINT"
SQ_HOME="{sq_home}"

DIGEST="sha256:$(sha256sum "$MANIFEST_PATH" | awk '{{print $1}}')"

PAYLOAD_FILE="$(mktemp)"
cat > "$PAYLOAD_FILE" <<EOF
{{"critical": {{"type": "atomic container signature", \
"image": {{"docker-manifest-digest": "$DIGEST"}}, \
"identity": {{"docker-reference": "$REFERENCE"}}}}, \
"optional": {{"creator": "pulp sq test"}}}}
EOF

sq --home "$SQ_HOME" sign --signer "$FINGERPRINT" --message --binary \
   --output "$SIG_PATH" "$PAYLOAD_FILE"

echo "{{\\"signature_path\\": \\"$SIG_PATH\\"}}"
"""


@pytest.fixture
def distribution(
    registry_client,
    local_registry,
    container_distribution_api,
    container_namespace_api,
    full_path,
    add_to_cleanup,
):
    """The fixture for a distribution created by pushing an image to the registry."""
    image_path = f"{REGISTRY_V2_REPO_PULP}:{MANIFEST_TAG}"
    registry_client.pull(image_path)
    local_registry.tag_and_push(image_path, full_path(f"test-1:{MANIFEST_TAG}"))

    distribution = container_distribution_api.list(name="test-1").results[0]
    # Clean up the namespace, which cascades to the distribution and the push repository.
    add_to_cleanup(container_namespace_api, distribution.namespace)

    return distribution


@pytest.fixture
def manifest_signing_service(signing_key_home, tmp_path, pulpcore_bindings):
    """Register a ManifestSigningService backed by a Sequoia key.

    Parameterized (via `signing_key_home`) over a key that signs with its primary key and
    one that signs with a dedicated subkey.
    """
    script_path = tmp_path / "sign-manifest.sh"
    script_path.write_text(SIGNING_SCRIPT_STRING.format(sq_home=signing_key_home.home))
    script_path.chmod(0o755)

    try:
        service_name = create_signing_service(
            signing_key_home.home,
            signing_key_home.fingerprint,
            script_path,
            backend="sq",
            service_class="container:ManifestSigningService",
        )
    except TypeError:
        pytest.skip("This pulpcore release does not support the Sequoia (sq) signing backend")

    service = pulpcore_bindings.SigningServicesApi.list(name=service_name).results[0]
    assert service.pubkey_fingerprint == signing_key_home.fingerprint

    yield service, signing_key_home.signing_fingerprint, signing_key_home.signing_keyid

    remove_signing_service(service_name, service_class="container:ManifestSigningService")


def test_sign_manifest(
    manifest_signing_service,
    distribution,
    container_repository_api,
    container_signature_api,
    container_tag_api,
    container_manifest_api,
    monitor_task,
):
    """Test whether a user can sign a manifest by leveraging a signing service.

    Runs against both primary-key and subkey signing.
    """
    service, fingerprint, keyid = manifest_signing_service
    sign_data = {"manifest_signing_service": service.pulp_href}

    response = container_repository_api.sign(distribution.repository, sign_data)
    created_resources = monitor_task(response.task).created_resources

    repository_version = created_resources[0]
    tags = container_tag_api.list(repository_version=repository_version)
    assert tags.count == 1

    tag = tags.results[0]
    assert tag.name == MANIFEST_TAG

    signatures = container_signature_api.list(repository_version=repository_version)
    assert signatures.count == 1

    signature = signatures.results[0]
    assert signature.key_id == keyid
    assert signature.fingerprint == fingerprint
    assert signature.type == SIGNATURE_TYPE.ATOMIC_SHORT

    manifest = container_manifest_api.read(tag.tagged_manifest)
    assert signature.signed_manifest == manifest.pulp_href
    assert signature.name.startswith(manifest.digest)

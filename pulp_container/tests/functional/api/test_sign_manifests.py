import pytest

from pulp_smash.pulp3.bindings import monitor_task

from pulpcore.client.pulp_container import RepositorySign

from pulp_container.constants import SIGNATURE_TYPE
from pulp_container.tests.functional.constants import REGISTRY_V2_REPO_PULP

MANIFEST_TAG = "manifest_a"


@pytest.fixture
def distribution(registry_client, local_registry, container_distribution_api, add_to_cleanup):
    """The fixture for a distribution that references a repository of the push type."""
    image_path = f"{REGISTRY_V2_REPO_PULP}:{MANIFEST_TAG}"
    registry_client.pull(image_path)
    local_registry.tag_and_push(image_path, f"test-1:{MANIFEST_TAG}")

    distribution = container_distribution_api.list(name="test-1").results[0]
    add_to_cleanup(container_distribution_api, distribution.pulp_href)

    return distribution


def test_sign_manifest(
    signing_gpg_metadata,
    distribution,
    container_signing_service,
    container_push_repository_api,
    container_signature_api,
    container_tag_api,
    container_manifest_api,
):
    """Test whether a user can sign a manifest by leveraging a signing service."""
    _, _, keyid = signing_gpg_metadata
    sign_data = RepositorySign(container_signing_service.pulp_href)

    response = container_push_repository_api.sign(distribution.repository, sign_data)
    created_resources = monitor_task(response.task).created_resources

    tags = container_tag_api.list(repository_version=created_resources[0])
    assert tags.count == 1

    tag = tags.results[0]
    assert tag.name == MANIFEST_TAG

    signatures = container_signature_api.list()
    assert signatures.count == 1

    signature = signatures.results[0]
    assert signature.key_id == keyid
    assert signature.type == SIGNATURE_TYPE.ATOMIC_SHORT

    manifest = container_manifest_api.read(tag.tagged_manifest)
    assert signature.signed_manifest == manifest.pulp_href
    assert signature.name.startswith(manifest.digest)

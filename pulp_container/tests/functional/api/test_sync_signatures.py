import pytest

from pulp_smash.pulp3.bindings import monitor_task
from pulp_smash.pulp3.utils import gen_repo

from pulpcore.client.pulp_container import (
    ContainerContainerRepository,
    ContainerRepositorySyncURL,
)
from pulp_container.tests.functional.utils import gen_container_remote

REDHAT_REGISTRY_V2 = "https://registry.access.redhat.com"
DEPRECATED_REPOSITORY_NAME = "rhel7-rhel-minimal"
IMAGE_MANIFEST_TAG = "7.9-511-source"
MANIFEST_LIST_TAG = "7.9"
SIGSTORE_URL = "https://access.redhat.com/webassets/docker/content/sigstore"


@pytest.fixture
def synced_repository(
    delete_orphans_pre,
    container_repository_api,
    container_remote_api,
    gen_object_with_cleanup,
    request,
):
    """A repository that contains signatures synced from sigstore, if specified."""
    data = gen_container_remote(
        url=REDHAT_REGISTRY_V2,
        upstream_name=DEPRECATED_REPOSITORY_NAME,
        policy="on_demand",
        include_tags=[MANIFEST_LIST_TAG, IMAGE_MANIFEST_TAG],
    )

    if request.param["sigstore"]:
        data["sigstore"] = request.param["sigstore"]

    remote = gen_object_with_cleanup(container_remote_api, data)

    data = ContainerContainerRepository(**gen_repo())
    repository = gen_object_with_cleanup(container_repository_api, data)

    signed_only = request.param["signed_only"]
    data = ContainerRepositorySyncURL(remote=remote.pulp_href, signed_only=signed_only)
    response = container_repository_api.sync(repository.pulp_href, data)
    monitor_task(response.task)

    return container_repository_api.read(repository.pulp_href)


@pytest.mark.parametrize(
    "synced_repository", [{"sigstore": None, "signed_only": False}], indirect=True
)
def test_sync_images_without_signatures(
    container_signature_api, container_tag_api, synced_repository
):
    """Sync a repository without specifying sigstore."""
    signatures = container_signature_api.list(
        repository_version=synced_repository.latest_version_href
    ).results
    assert len(signatures) == 0

    tags = container_tag_api.list(repository_version=synced_repository.latest_version_href).results
    assert len(tags) == 2


@pytest.mark.parametrize(
    "synced_repository",
    # all the content served on the URL is signed and it should not affect sync tasks
    [
        {"sigstore": SIGSTORE_URL, "signed_only": True},
        {"sigstore": SIGSTORE_URL, "signed_only": False},
    ],
    indirect=True,
)
def test_sync_signed_images_from_sigstore(
    container_signature_api, container_manifest_api, container_tag_api, synced_repository
):
    """Sync a repository with specifying sigstore."""
    signatures = container_signature_api.list(
        repository_version=synced_repository.latest_version_href
    ).results
    tags = container_tag_api.list(repository_version=synced_repository.latest_version_href).results

    tags_dict = {tag.name: tag for tag in tags}

    single_manifest_href = tags_dict[IMAGE_MANIFEST_TAG].tagged_manifest
    manifest = container_manifest_api.read(single_manifest_href)

    single_manifest_signatures = list(
        filter(lambda s: s.signed_manifest == manifest.pulp_href, signatures)
    )

    # single manifest (2 signatures in total)
    # 2 signatures for d13348c6ced8b932b9a3d21e7276f2a2b6b63a7e285a373ca289f045bfd3531c
    assert len(single_manifest_signatures) == 2
    assert all(s.name.startswith(manifest.digest) for s in single_manifest_signatures)

    manifest_list_href = tags_dict[MANIFEST_LIST_TAG].tagged_manifest
    manifest_list = container_manifest_api.read(manifest_list_href)

    listed_manifests = [
        container_manifest_api.read(lm_href) for lm_href in manifest_list.listed_manifests
    ]
    for lm in listed_manifests:
        manifest_signatures = list(filter(lambda s: lm.pulp_href == s.signed_manifest, signatures))
        assert all(s.name.startswith(lm.digest) for s in manifest_signatures)

        # listed_manifests (18 signatures in total)
        # 6 signatures for 6577ee9adfb61703e68549261d4665b2641eb6a51162bafc398e3b89cae6fef5
        # 6 signatures for c2a2c14a60dfb486ad52f11a6b202492256c6b249aeff267cbd859dc4225d0ad
        # 6 signatures for cccaa4cd19f04183ebb359bc3fdba9742aa56bb1bac2b5d9703c6f1a40b0f8ec
        assert len(manifest_signatures) == 6


@pytest.mark.parametrize(
    "synced_repository", [{"sigstore": None, "signed_only": True}], indirect=True
)
def test_sync_images_without_sigstore_requiring_signatures(
    container_signature_api, container_tag_api, synced_repository
):
    """Sync a repository with no sigstore but with the signed_only option enabled."""
    signatures = container_signature_api.list(
        repository_version=synced_repository.latest_version_href
    ).results
    assert len(signatures) == 0

    tags = container_tag_api.list(repository_version=synced_repository.latest_version_href).results
    assert len(tags) == 0

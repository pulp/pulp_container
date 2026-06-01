"""Tests for deleting manifests via the Docker v2 API."""

import time
from urllib.parse import urljoin

import pytest
import requests

from pulp_container.tests.functional.constants import REGISTRY_V2_REPO_PULP


def _wait_for_tag(container_bindings, repository_href, tag_name, present, timeout=60):
    for _ in range(timeout):
        repository = container_bindings.RepositoriesContainerPushApi.read(repository_href)
        tags = container_bindings.ContentTagsApi.list(
            name=tag_name, repository_version=repository.latest_version_href
        )
        if bool(tags.results) == present:
            if present:
                return tags.results[0].tagged_manifest
            return None
        time.sleep(1)
    if present:
        pytest.fail(f"Tag '{tag_name}' was not available in the repository")
    pytest.fail(f"Tag '{tag_name}' was not removed from the repository")


def test_delete_manifest_by_digest(
    add_to_cleanup,
    local_registry,
    registry_client,
    container_bindings,
    full_path,
):
    """Delete a manifest by digest via DELETE /v2/<name>/manifests/<digest>."""
    repo_name = "delete/manifest"
    local_url = full_path(f"{repo_name}:manifest_a")
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    registry_client.pull(image_path)
    local_registry.tag_and_push(image_path, local_url)

    namespace = container_bindings.PulpContainerNamespacesApi.list(name="delete").results[0]
    add_to_cleanup(container_bindings.PulpContainerNamespacesApi, namespace.pulp_href)

    repository = container_bindings.RepositoriesContainerPushApi.list(name=repo_name).results[0]
    manifest_href = _wait_for_tag(
        container_bindings, repository.pulp_href, "manifest_a", present=True
    )
    digest = container_bindings.ContentManifestsApi.read(manifest_href).digest

    delete_path = f"/v2/{full_path(repo_name)}/manifests/{digest}"
    response, _ = local_registry.get_response("DELETE", delete_path)
    assert response.status_code == 202

    _wait_for_tag(container_bindings, repository.pulp_href, "manifest_a", present=False)


def test_delete_manifest_by_tag_rejected(
    add_to_cleanup,
    local_registry,
    registry_client,
    container_bindings,
    full_path,
):
    """Delete by tag name is not allowed."""
    repo_name = "delete/by-tag"
    local_url = full_path(f"{repo_name}:manifest_a")
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    registry_client.pull(image_path)
    local_registry.tag_and_push(image_path, local_url)

    namespace = container_bindings.PulpContainerNamespacesApi.list(name="delete").results[0]
    add_to_cleanup(container_bindings.PulpContainerNamespacesApi, namespace.pulp_href)

    delete_path = f"/v2/{full_path(repo_name)}/manifests/manifest_a"
    response, _ = local_registry.get_response("DELETE", delete_path)
    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "INVALID_REQUEST"


def test_delete_manifest_not_found(
    add_to_cleanup,
    local_registry,
    registry_client,
    container_bindings,
    full_path,
):
    """Deleting a non-existent manifest returns 404."""
    repo_name = "delete/not-found"
    local_url = full_path(f"{repo_name}:manifest_a")
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    registry_client.pull(image_path)
    local_registry.tag_and_push(image_path, local_url)

    namespace = container_bindings.PulpContainerNamespacesApi.list(name="delete").results[0]
    add_to_cleanup(container_bindings.PulpContainerNamespacesApi, namespace.pulp_href)

    digest = f"sha256:{'0' * 64}"
    delete_path = f"/v2/{full_path(repo_name)}/manifests/{digest}"
    response, _ = local_registry.get_response("DELETE", delete_path)
    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "MANIFEST_UNKNOWN"


def test_delete_manifest_without_login(
    add_to_cleanup,
    anonymous_user,
    bindings_cfg,
    container_bindings,
    full_path,
    local_registry,
    registry_client,
):
    """Delete requires authentication."""
    repo_name = "delete/unauth"
    local_url = full_path(f"{repo_name}:manifest_a")
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    registry_client.pull(image_path)
    local_registry.tag_and_push(image_path, local_url)

    namespace = container_bindings.PulpContainerNamespacesApi.list(name="delete").results[0]
    add_to_cleanup(container_bindings.PulpContainerNamespacesApi, namespace.pulp_href)

    repository = container_bindings.RepositoriesContainerPushApi.list(name=repo_name).results[0]
    manifest_href = _wait_for_tag(
        container_bindings, repository.pulp_href, "manifest_a", present=True
    )
    digest = container_bindings.ContentManifestsApi.read(manifest_href).digest

    delete_path = f"/v2/{full_path(repo_name)}/manifests/{digest}"
    url = urljoin(bindings_cfg.host, delete_path)
    with anonymous_user:
        response = requests.delete(url, trust_env=False)
    assert response.status_code == 401

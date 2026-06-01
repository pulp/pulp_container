"""Tests for deleting manifests via the Docker v2 API."""

import time

import pytest

from pulp_container.tests.functional.constants import REGISTRY_V2_REPO_PULP


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

    head_path = f"/v2/{full_path(repo_name)}/manifests/manifest_a"
    response, _ = local_registry.get_response("HEAD", head_path)
    assert response.status_code == 200
    digest = response.headers["Docker-Content-Digest"]

    delete_path = f"/v2/{full_path(repo_name)}/manifests/{digest}"
    response, _ = local_registry.get_response("DELETE", delete_path)
    assert response.status_code == 202

    for _ in range(60):
        response, _ = local_registry.get_response("HEAD", head_path)
        if response.status_code == 404:
            break
        time.sleep(1)
    else:
        pytest.fail("Manifest was not removed from the repository")


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
    anonymous_user,
    local_registry,
    full_path,
):
    """Delete requires authentication."""
    digest = f"sha256:{'0' * 64}"
    delete_path = f"/v2/{full_path('delete/unauth')}/manifests/{digest}"
    with anonymous_user:
        response, _ = local_registry.get_response("DELETE", delete_path)
    assert response.status_code == 401

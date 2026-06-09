"""Tests for deleting blobs via the Docker v2 API."""

from pulp_container.tests.functional.constants import REGISTRY_V2_REPO_PULP


def test_delete_pending_blob(
    add_to_cleanup,
    local_registry,
    registry_client,
    container_bindings,
    full_path,
):
    """Delete a pending blob via DELETE /v2/<name>/blobs/<digest>."""
    source_repo = "delete/blob-source"
    dest_repo = "delete/blob-pending"
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    registry_client.pull(image_path)
    local_registry.tag_and_push(image_path, full_path(f"{source_repo}:manifest_a"))

    namespace = container_bindings.PulpContainerNamespacesApi.list(name="delete").results[0]
    add_to_cleanup(container_bindings.PulpContainerNamespacesApi, namespace.pulp_href)

    repository = container_bindings.RepositoriesContainerApi.list(name=source_repo).results[0]
    blob = container_bindings.ContentBlobsApi.list(
        repository_version=repository.latest_version_href
    ).results[0]

    mount_path = (
        f"/v2/{full_path(dest_repo)}/blobs/uploads/"
        f"?from={full_path(source_repo)}&mount={blob.digest}"
    )
    response, _ = local_registry.get_response("POST", mount_path)
    assert response.status_code == 201

    delete_path = f"/v2/{full_path(dest_repo)}/blobs/{blob.digest}"
    response, _ = local_registry.get_response("DELETE", delete_path)
    assert response.status_code == 202

    head_path = f"/v2/{full_path(dest_repo)}/blobs/{blob.digest}"
    response, _ = local_registry.get_response("HEAD", head_path)
    assert response.status_code == 404
    assert response.headers.get("Docker-Distribution-Api-Version") == "registry/2.0"


def test_delete_blob_not_found(
    add_to_cleanup,
    local_registry,
    registry_client,
    container_bindings,
    full_path,
):
    """Deleting a non-existent blob returns 404."""
    repo_name = "delete/blob-not-found"
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    registry_client.pull(image_path)
    local_registry.tag_and_push(image_path, full_path(f"{repo_name}:manifest_a"))

    namespace = container_bindings.PulpContainerNamespacesApi.list(name="delete").results[0]
    add_to_cleanup(container_bindings.PulpContainerNamespacesApi, namespace.pulp_href)

    digest = f"sha256:{'0' * 64}"
    delete_path = f"/v2/{full_path(repo_name)}/blobs/{digest}"
    response, _ = local_registry.get_response("DELETE", delete_path)
    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "BLOB_UNKNOWN"


def test_delete_blob_invalid_digest(
    add_to_cleanup,
    local_registry,
    registry_client,
    container_bindings,
    full_path,
):
    """Delete requires a sha256 digest."""
    repo_name = "delete/blob-invalid"
    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    registry_client.pull(image_path)
    local_registry.tag_and_push(image_path, full_path(f"{repo_name}:manifest_a"))

    namespace = container_bindings.PulpContainerNamespacesApi.list(name="delete").results[0]
    add_to_cleanup(container_bindings.PulpContainerNamespacesApi, namespace.pulp_href)

    delete_path = f"/v2/{full_path(repo_name)}/blobs/not-a-digest"
    response, _ = local_registry.get_response("DELETE", delete_path)
    assert response.status_code == 400
    assert response.json()["errors"][0]["code"] == "INVALID_REQUEST"


def test_delete_blob_without_login(
    anonymous_user,
    local_registry,
    full_path,
):
    """Delete requires authentication."""
    digest = f"sha256:{'0' * 64}"
    delete_path = f"/v2/{full_path('delete/blob-unauth')}/blobs/{digest}"
    with anonymous_user:
        response, _ = local_registry.get_response("DELETE", delete_path)
    assert response.status_code == 401

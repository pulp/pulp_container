"""Tests that verify blob uploads can be cancelled via the registry API."""

import uuid

import pytest

from pulp_container.app import models


def test_cancel_blob_upload(local_registry, container_bindings, full_path, add_to_cleanup):
    """Test cancelling an outstanding blob upload."""
    repo_name = f"cancel-upload/{uuid.uuid4()}"
    upload_path = f"/v2/{full_path(repo_name)}/blobs/uploads/"

    response, _ = local_registry.get_response("POST", upload_path)
    assert response.status_code == 202
    upload_uuid = response.headers["Docker-Upload-UUID"]

    distribution = container_bindings.DistributionsContainerApi.list(name=repo_name).results[0]
    add_to_cleanup(container_bindings.PulpContainerNamespacesApi, distribution.namespace)

    assert models.Upload.objects.filter(pk=upload_uuid).exists()

    delete_path = f"/v2/{full_path(repo_name)}/blobs/uploads/{upload_uuid}"
    response, _ = local_registry.get_response("DELETE", delete_path)
    assert response.status_code == 204
    assert response.content == b""
    assert not models.Upload.objects.filter(pk=upload_uuid).exists()


def test_cancel_unknown_blob_upload(local_registry, full_path, add_to_cleanup, container_bindings):
    """Test cancelling a blob upload that does not exist."""
    repo_name = f"cancel-upload/{uuid.uuid4()}"
    upload_path = f"/v2/{full_path(repo_name)}/blobs/uploads/"

    response, _ = local_registry.get_response("POST", upload_path)
    assert response.status_code == 202

    distribution = container_bindings.DistributionsContainerApi.list(name=repo_name).results[0]
    add_to_cleanup(container_bindings.PulpContainerNamespacesApi, distribution.namespace)

    upload_uuid = uuid.uuid4()
    delete_path = f"/v2/{full_path(repo_name)}/blobs/uploads/{upload_uuid}"

    response, _ = local_registry.get_response("DELETE", delete_path)
    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "BLOB_UPLOAD_UNKNOWN"


def test_cancel_blob_upload_without_permission(
    gen_user, local_registry, full_path, pulp_settings, add_to_cleanup, container_bindings
):
    """Test that cancelling a blob upload requires push permission."""
    if pulp_settings.TOKEN_AUTH_DISABLED:
        pytest.skip("RBAC cannot be tested when token authentication is disabled")

    user_helpless = gen_user()
    repo_name = f"cancel-upload/{uuid.uuid4()}"
    upload_path = f"/v2/{full_path(repo_name)}/blobs/uploads/"

    response, _ = local_registry.get_response("POST", upload_path)
    assert response.status_code == 202
    upload_uuid = response.headers["Docker-Upload-UUID"]

    distribution = container_bindings.DistributionsContainerApi.list(name=repo_name).results[0]
    add_to_cleanup(container_bindings.PulpContainerNamespacesApi, distribution.namespace)

    delete_path = f"/v2/{full_path(repo_name)}/blobs/uploads/{upload_uuid}"
    with user_helpless:
        response, _ = local_registry.get_response("DELETE", delete_path)
        assert response.status_code == 401

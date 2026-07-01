"""Tests for cancelling blob uploads via the Docker v2 API."""

import uuid

import pytest

from pulp_container.app import models


class TestCancelBlobUpload:
    """Tests for DELETE /v2/<name>/blobs/uploads/<uuid>."""

    repo_name = "cancel/upload"

    @pytest.fixture(scope="class")
    def setup(
        self,
        add_to_cleanup,
        container_bindings,
        local_registry,
        full_path,
    ):
        """Create a push repository and blob upload for all cancel blob upload tests."""
        upload_path = f"/v2/{full_path(self.repo_name)}/blobs/uploads/"
        response, _ = local_registry.get_response("POST", upload_path)
        assert response.status_code == 202

        distribution = container_bindings.DistributionsContainerApi.list(name=self.repo_name).results[0]
        add_to_cleanup(container_bindings.PulpContainerNamespacesApi, distribution.namespace)

        upload_uuid = response.headers["Docker-Upload-UUID"]
        return upload_uuid

    def test_01_cancel_unknown_blob_upload(self, setup, local_registry, full_path):
        """Cancelling a blob upload that does not exist returns 404."""
        upload_uuid = uuid.uuid4()
        delete_path = f"/v2/{full_path(self.repo_name)}/blobs/uploads/{upload_uuid}"
        response, _ = local_registry.get_response("DELETE", delete_path)
        assert response.status_code == 404
        assert response.json()["errors"][0]["code"] == "BLOB_UPLOAD_UNKNOWN"

    def test_02_cancel_blob_upload_without_permission(self, setup, gen_user, local_registry, full_path):
        """Cancel requires push permissions on the namespace."""
        upload_uuid = setup
        delete_path = f"/v2/{full_path(self.repo_name)}/blobs/uploads/{upload_uuid}"
        user_helpless = gen_user()
        with user_helpless:
            response, _ = local_registry.get_response("DELETE", delete_path)
        assert response.status_code in (401, 403)

    def test_03_cancel_blob_upload(self, setup, local_registry, full_path):
        """Cancel an outstanding blob upload via DELETE /v2/<name>/blobs/uploads/<uuid>."""
        upload_uuid = setup
        assert models.Upload.objects.filter(pk=upload_uuid).exists()

        delete_path = f"/v2/{full_path(self.repo_name)}/blobs/uploads/{upload_uuid}"
        response, _ = local_registry.get_response("DELETE", delete_path)
        assert response.status_code == 204
        assert response.content == b""
        assert not models.Upload.objects.filter(pk=upload_uuid).exists()

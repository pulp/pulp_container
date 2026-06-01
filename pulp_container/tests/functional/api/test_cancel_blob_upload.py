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
        """Create a push repository for all cancel blob upload tests."""
        upload_path = f"/v2/{full_path(self.repo_name)}/blobs/uploads/"
        response, _ = local_registry.get_response("POST", upload_path)
        assert response.status_code == 202

        distribution = container_bindings.DistributionsContainerApi.list(name=self.repo_name).results[0]
        add_to_cleanup(container_bindings.PulpContainerNamespacesApi, distribution.namespace)

        upload_uuid = response.headers["Docker-Upload-UUID"]
        delete_path = f"/v2/{full_path(self.repo_name)}/blobs/uploads/{upload_uuid}"
        local_registry.get_response("DELETE", delete_path)

    def _start_upload(self, local_registry, full_path):
        upload_path = f"/v2/{full_path(self.repo_name)}/blobs/uploads/"
        response, _ = local_registry.get_response("POST", upload_path)
        assert response.status_code == 202
        return response.headers["Docker-Upload-UUID"]

    def test_01_cancel_unknown_blob_upload(self, setup, local_registry, full_path):
        """Cancelling a blob upload that does not exist returns 404."""
        upload_uuid = uuid.uuid4()
        delete_path = f"/v2/{full_path(self.repo_name)}/blobs/uploads/{upload_uuid}"
        response, _ = local_registry.get_response("DELETE", delete_path)
        assert response.status_code == 404
        assert response.json()["errors"][0]["code"] == "BLOB_UPLOAD_UNKNOWN"

    def test_02_cancel_blob_upload_without_permission(
        self, setup, gen_user, local_registry, full_path, pulp_settings
    ):
        """Cancel requires push permissions on the namespace."""
        if pulp_settings.TOKEN_AUTH_DISABLED:
            pytest.skip("RBAC cannot be tested when token authentication is disabled")

        upload_uuid = self._start_upload(local_registry, full_path)
        delete_path = f"/v2/{full_path(self.repo_name)}/blobs/uploads/{upload_uuid}"
        user_helpless = gen_user()
        with user_helpless:
            response, _ = local_registry.get_response("DELETE", delete_path)
        assert response.status_code == 401

    def test_03_cancel_blob_upload(self, setup, local_registry, full_path):
        """Cancel an outstanding blob upload via DELETE /v2/<name>/blobs/uploads/<uuid>."""
        upload_uuid = self._start_upload(local_registry, full_path)
        assert models.Upload.objects.filter(pk=upload_uuid).exists()

        delete_path = f"/v2/{full_path(self.repo_name)}/blobs/uploads/{upload_uuid}"
        response, _ = local_registry.get_response("DELETE", delete_path)
        assert response.status_code == 204
        assert response.content == b""
        assert not models.Upload.objects.filter(pk=upload_uuid).exists()

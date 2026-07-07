"""Tests for cancelling blob uploads via the Docker v2 API."""

import uuid

import pytest


def _start_blob_upload(local_registry, full_path, repo_name):
    upload_path = f"/v2/{full_path(repo_name)}/blobs/uploads/"
    response, _ = local_registry.get_response("POST", upload_path)
    assert response.status_code == 202
    return response.headers["Docker-Upload-UUID"]


class TestCancelBlobUpload:
    """Tests for DELETE /v2/<name>/blobs/uploads/<uuid>."""

    repo_name = "cancel/upload"

    @pytest.fixture(scope="class")
    def setup(
        self,
        add_to_cleanup,
        container_bindings,
        container_repository_factory,
        container_distribution_factory,
    ):
        """Create a push repository and distribution for all cancel blob upload tests."""
        repository = container_repository_factory()
        distribution = container_distribution_factory(
            name=self.repo_name,
            base_path=self.repo_name,
            repository=repository.pulp_href,
        )
        namespace = container_bindings.PulpContainerNamespacesApi.read(distribution.namespace)
        add_to_cleanup(container_bindings.PulpContainerNamespacesApi, namespace.pulp_href)

    def test_01_cancel_unknown_blob_upload(self, setup, local_registry, full_path):
        """Cancelling a blob upload that does not exist returns 404."""
        upload_uuid = uuid.uuid4()
        delete_path = f"/v2/{full_path(self.repo_name)}/blobs/uploads/{upload_uuid}"
        response, _ = local_registry.get_response("DELETE", delete_path)
        assert response.status_code == 404
        assert response.json()["errors"][0]["code"] == "BLOB_UPLOAD_UNKNOWN"

    def test_02_cancel_blob_upload_without_permission(
        self, setup, gen_user, local_registry, full_path
    ):
        """Cancel requires push permissions on the namespace."""
        upload_uuid = _start_blob_upload(local_registry, full_path, self.repo_name)
        delete_path = f"/v2/{full_path(self.repo_name)}/blobs/uploads/{upload_uuid}"
        user_helpless = gen_user()
        with user_helpless:
            response, _ = local_registry.get_response("DELETE", delete_path)
        assert response.status_code in (401, 403)

    def test_03_cancel_blob_upload(self, setup, local_registry, full_path):
        """Cancel an outstanding blob upload via DELETE /v2/<name>/blobs/uploads/<uuid>."""
        upload_uuid = _start_blob_upload(local_registry, full_path, self.repo_name)
        upload_path = f"/v2/{full_path(self.repo_name)}/blobs/uploads/{upload_uuid}"

        response, _ = local_registry.get_response("GET", upload_path)
        assert response.status_code == 204
        assert response.headers["Docker-Upload-UUID"] == upload_uuid

        response, _ = local_registry.get_response("DELETE", upload_path)
        assert response.status_code == 204
        assert response.content == b""

        response, _ = local_registry.get_response("GET", upload_path)
        assert response.status_code == 404

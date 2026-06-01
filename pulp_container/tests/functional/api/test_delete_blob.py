"""Tests for deleting blobs via the Docker v2 API."""

import time

import pytest

from pulp_container.tests.functional.constants import PULP_FIXTURE_1


def _wait_for_blob(container_bindings, repository_href, digest, present, timeout=60):
    for _ in range(timeout):
        repository = container_bindings.RepositoriesContainerApi.read(repository_href)
        blobs = container_bindings.ContentBlobsApi.list(
            digest=digest, repository_version=repository.latest_version_href
        )
        if bool(blobs.results) == present:
            if present:
                return blobs.results[0]
            return None
        time.sleep(1)
    if present:
        pytest.fail(f"Blob '{digest}' was not available in the repository")
    pytest.fail(f"Blob '{digest}' was not removed from the repository")


class TestDeleteBlob:
    """Tests for DELETE /v2/<name>/blobs/<digest>.

    Tests are numbered so failure cases run before the success cases that modify
    the shared class-scoped repository.
    """

    repo_name = "delete/blob"
    dest_repo_name = "delete/blob-pending"
    tag_name = "manifest_a"

    @pytest.fixture(scope="class")
    def setup(
        self,
        add_to_cleanup,
        container_bindings,
        container_repository_factory,
        container_remote_factory,
        container_sync,
        container_distribution_factory,
    ):
        """Sync an image once for all delete blob tests."""
        repository = container_repository_factory()
        remote = container_remote_factory(upstream_name=PULP_FIXTURE_1, includes=[self.tag_name])
        container_sync(repository, remote)
        repository = container_bindings.RepositoriesContainerApi.read(repository.pulp_href)

        distribution = container_distribution_factory(
            name=self.repo_name,
            base_path=self.repo_name,
            repository=repository.pulp_href,
        )
        namespace = container_bindings.PulpContainerNamespacesApi.read(distribution.namespace)
        add_to_cleanup(container_bindings.PulpContainerNamespacesApi, namespace.pulp_href)

        dest_repository = container_repository_factory()
        container_distribution_factory(
            name=self.dest_repo_name,
            base_path=self.dest_repo_name,
            repository=dest_repository.pulp_href,
        )

        blob = container_bindings.ContentBlobsApi.list(
            repository_version=repository.latest_version_href
        ).results[0]

        return repository, blob.digest

    def test_01_delete_invalid_digest(self, setup, local_registry, full_path):
        """Delete requires a sha256 digest."""
        delete_path = f"/v2/{full_path(self.repo_name)}/blobs/not-a-digest"
        response, _ = local_registry.get_response("DELETE", delete_path)
        assert response.status_code == 400
        assert response.json()["errors"][0]["code"] == "INVALID_REQUEST"

    def test_02_delete_not_found(self, setup, local_registry, full_path):
        """Deleting a non-existent blob returns 404."""
        digest = f"sha256:{'0' * 64}"
        delete_path = f"/v2/{full_path(self.repo_name)}/blobs/{digest}"
        response, _ = local_registry.get_response("DELETE", delete_path)
        assert response.status_code == 404
        assert response.json()["errors"][0]["code"] == "BLOB_UNKNOWN"

    def test_03_delete_without_login(self, setup, gen_user, local_registry, full_path):
        """Delete requires push permissions on the namespace."""
        _, digest = setup
        delete_path = f"/v2/{full_path(self.repo_name)}/blobs/{digest}"
        user_helpless = gen_user()
        with user_helpless:
            response, _ = local_registry.get_response("DELETE", delete_path)
        assert response.status_code in (401, 403)

    def test_04_delete_pending_blob(self, setup, local_registry, full_path):
        """Delete a pending blob via DELETE /v2/<name>/blobs/<digest>."""
        _, digest = setup
        mount_path = (
            f"/v2/{full_path(self.dest_repo_name)}/blobs/uploads/"
            f"?from={full_path(self.repo_name)}&mount={digest}"
        )
        response, _ = local_registry.get_response("POST", mount_path)
        assert response.status_code == 201

        delete_path = f"/v2/{full_path(self.dest_repo_name)}/blobs/{digest}"
        response, _ = local_registry.get_response("DELETE", delete_path)
        assert response.status_code == 202

        head_path = f"/v2/{full_path(self.dest_repo_name)}/blobs/{digest}"
        response, _ = local_registry.get_response("HEAD", head_path)
        assert response.status_code == 404

    def test_05_delete_by_digest(self, setup, local_registry, container_bindings, full_path):
        """Delete a committed blob by digest via DELETE /v2/<name>/blobs/<digest>."""
        repository, digest = setup
        delete_path = f"/v2/{full_path(self.repo_name)}/blobs/{digest}"
        response, _ = local_registry.get_response("DELETE", delete_path)
        assert response.status_code == 202

        _wait_for_blob(container_bindings, repository.pulp_href, digest, present=False)

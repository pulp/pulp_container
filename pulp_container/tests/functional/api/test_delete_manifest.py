"""Tests for deleting manifests via the Docker v2 API."""

import time

import pytest

from pulp_container.tests.functional.constants import PULP_FIXTURE_1


def _wait_for_tag(container_bindings, repository_href, tag_name, present, timeout=60):
    for _ in range(timeout):
        repository = container_bindings.RepositoriesContainerApi.read(repository_href)
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


class TestDeleteManifest:
    """Tests for DELETE /v2/<name>/manifests/<reference>."""

    repo_name = "delete/manifest"
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
        """Sync an image once for all delete manifest tests."""
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

        manifest_href = (
            container_bindings.ContentTagsApi.list(
                name=self.tag_name, repository_version=repository.latest_version_href
            )
            .results[0]
            .tagged_manifest
        )
        digest = container_bindings.ContentManifestsApi.read(manifest_href).digest
        return repository, digest

    def test_01_delete_by_tag_rejected(self, setup, local_registry, full_path):
        """Delete by tag name is not allowed."""
        delete_path = f"/v2/{full_path(self.repo_name)}/manifests/{self.tag_name}"
        response, _ = local_registry.get_response("DELETE", delete_path)
        assert response.status_code == 400
        assert response.json()["errors"][0]["code"] == "INVALID_REQUEST"

    def test_02_delete_not_found(self, setup, local_registry, full_path):
        """Deleting a non-existent manifest returns 404."""
        digest = f"sha256:{'0' * 64}"
        delete_path = f"/v2/{full_path(self.repo_name)}/manifests/{digest}"
        response, _ = local_registry.get_response("DELETE", delete_path)
        assert response.status_code == 404
        assert response.json()["errors"][0]["code"] == "MANIFEST_UNKNOWN"

    def test_03_delete_without_login(self, setup, gen_user, local_registry, full_path):
        """Delete requires push permissions on the namespace."""
        _, digest = setup
        delete_path = f"/v2/{full_path(self.repo_name)}/manifests/{digest}"
        user_helpless = gen_user()
        with user_helpless:
            response, _ = local_registry.get_response("DELETE", delete_path)
        assert response.status_code in (401, 403)

    def test_04_delete_by_digest(self, setup, local_registry, container_bindings, full_path):
        """Delete a manifest by digest via DELETE /v2/<name>/manifests/<digest>."""
        repository, digest = setup
        delete_path = f"/v2/{full_path(self.repo_name)}/manifests/{digest}"
        response, _ = local_registry.get_response("DELETE", delete_path)
        assert response.status_code == 202

        _wait_for_tag(container_bindings, repository.pulp_href, self.tag_name, present=False)

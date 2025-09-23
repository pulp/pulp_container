"""
Tests PulpExporter and PulpImporter functionality

NOTE: assumes ALLOWED_EXPORT_PATHS setting contains "/tmp" - all tests will fail if this is not
the case.
"""

import pytest
import uuid

from pulp_container.tests.functional.constants import REGISTRY_V2_REPO_PULP


def test_import_export_standard(
    local_registry,
    container_bindings,
    container_repository_factory,
    container_remote_factory,
    container_distribution_factory,
    container_sync,
    pulpcore_bindings,
    full_path,
    gen_object_with_cleanup,
    has_pulp_plugin,
    monitor_task,
    monitor_task_group,
    pulp_settings,
):
    """Test exporting and importing of a container repository."""
    if pulp_settings.DOMAIN_ENABLED and not has_pulp_plugin("core", min="3.90.0"):
        pytest.skip("Pulp Import/Export only supported under domains in core>=3.90")

    remote = container_remote_factory()
    repository = container_repository_factory()
    container_sync(repository, remote)

    # Export the repository
    body = {
        "name": str(uuid.uuid4()),
        "path": f"/tmp/{uuid.uuid4()}/",
        "repositories": [repository.pulp_href],
    }
    exporter = gen_object_with_cleanup(pulpcore_bindings.ExportersPulpApi, body)

    export_response = pulpcore_bindings.ExportersPulpExportsApi.create(exporter.pulp_href, {})
    export_href = monitor_task(export_response.task).created_resources[0]
    export = pulpcore_bindings.ExportersPulpExportsApi.read(export_href)

    # Clean the old repository out
    monitor_task(
        container_bindings.RepositoriesContainerVersionsApi.delete(
            repository.latest_version_href
        ).task
    )
    monitor_task(pulpcore_bindings.OrphansCleanupApi.cleanup({"orphan_protection_time": 0}).task)

    # Import the repository
    import_repository = container_repository_factory()

    body = {
        "name": str(uuid.uuid4()),
        "repo_mapping": {repository.name: import_repository.name},
    }
    importer = gen_object_with_cleanup(pulpcore_bindings.ImportersPulpApi, body)

    if has_pulp_plugin("core", min="3.36.0"):
        filenames = [f for f in list(export.output_file_info.keys()) if f.endswith(".tar")]
    else:
        filenames = [f for f in list(export.output_file_info.keys()) if f.endswith("tar.gz")]

    import_response = pulpcore_bindings.ImportersPulpImportsApi.create(
        importer.pulp_href, {"path": filenames[0]}
    )
    if hasattr(import_response, "task_group"):
        task_group_href = import_response.task_group
    else:
        task_group_href = monitor_task(import_response.task).created_resources[1]
    monitor_task_group(task_group_href)

    # Verify that the imported repository contains the right associations
    import_repository = container_bindings.RepositoriesContainerApi.read(
        import_repository.pulp_href
    )
    manifests = container_bindings.ContentManifestsApi.list(
        repository_version=import_repository.latest_version_href
    ).results

    for manifest in manifests:
        if "manifest.list" in manifest.media_type:
            assert manifest.listed_manifests != []
        else:
            assert manifest.blobs != []
            assert manifest.config_blob is not None

    distribution_path = str(uuid.uuid4())
    distribution = container_distribution_factory(
        name=distribution_path, base_path=distribution_path, repository=import_repository.pulp_href
    )
    local_registry.pull(f"{full_path(distribution)}@{manifest.digest}")


def test_import_export_create_repositories(
    registry_client,
    local_registry,
    container_bindings,
    container_distribution_factory,
    pulpcore_bindings,
    full_path,
    gen_object_with_cleanup,
    has_pulp_plugin,
    monitor_task,
    monitor_task_group,
    pulp_settings,
):
    """Test importing of a push repository without creating an initial repository manually."""
    if registry_client.name != "podman":
        pytest.skip("This test requires podman to push pulled content", allow_module_level=True)

    if pulp_settings.DOMAIN_ENABLED and not has_pulp_plugin("core", min="3.90.0"):
        pytest.skip("Pulp Import/Export only supported under domains in core>=3.90")

    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    registry_client.pull(image_path)

    distribution_path = str(uuid.uuid4())
    local_registry.tag_and_push(image_path, f"{full_path(distribution_path)}:manifest_a")

    distribution = container_bindings.DistributionsContainerApi.list(
        name=distribution_path
    ).results[0]

    body = {
        "name": str(uuid.uuid4()),
        "path": f"/tmp/{uuid.uuid4()}/",
        "repositories": [distribution.repository],
    }
    exporter = gen_object_with_cleanup(pulpcore_bindings.ExportersPulpApi, body)
    export_response = pulpcore_bindings.ExportersPulpExportsApi.create(exporter.pulp_href, {})
    export_href = monitor_task(export_response.task).created_resources[0]
    export = pulpcore_bindings.ExportersPulpExportsApi.read(export_href)

    # Clean the old repository out
    monitor_task(container_bindings.DistributionsContainerApi.delete(distribution.pulp_href).task)
    monitor_task(pulpcore_bindings.OrphansCleanupApi.cleanup({"orphan_protection_time": 0}).task)

    body = {"name": str(uuid.uuid4())}
    importer = gen_object_with_cleanup(pulpcore_bindings.ImportersPulpApi, body)

    if has_pulp_plugin("core", min="3.36.0"):
        filenames = [f for f in list(export.output_file_info.keys()) if f.endswith(".tar")]
    else:
        filenames = [f for f in list(export.output_file_info.keys()) if f.endswith("tar.gz")]

    import_response = pulpcore_bindings.ImportersPulpImportsApi.create(
        importer.pulp_href, {"path": filenames[0], "create_repositories": True}
    )
    if hasattr(import_response, "task_group"):
        task_group_href = import_response.task_group
    else:
        task_group_href = monitor_task(import_response.task).created_resources[1]
    monitor_task_group(task_group_href)

    repositories = container_bindings.RepositoriesContainerApi.list(name=distribution_path).results
    assert len(repositories) == 1

    tags = container_bindings.ContentTagsApi.list(
        name="manifest_a", repository_version=repositories[0].latest_version_href
    ).results
    assert len(tags) == 1

    manifests = container_bindings.ContentManifestsApi.list(
        repository_version=repositories[0].latest_version_href
    ).results

    for manifest in manifests:
        if "manifest.list" in manifest.media_type:
            assert manifest.listed_manifests != []
        else:
            assert manifest.blobs != []
            assert manifest.config_blob is not None

    distribution = {
        "name": distribution_path,
        "base_path": distribution_path,
        "repository": repositories[0].pulp_href,
    }
    distribution = container_distribution_factory(**distribution)
    local_registry.pull(f"{full_path(distribution)}:manifest_a")

    monitor_task(container_bindings.RepositoriesContainerApi.delete(repositories[0].pulp_href).task)
    monitor_task(pulpcore_bindings.OrphansCleanupApi.cleanup({"orphan_protection_time": 0}).task)

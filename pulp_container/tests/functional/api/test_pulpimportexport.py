"""
Tests PulpExporter and PulpImporter functionality

NOTE: assumes ALLOWED_EXPORT_PATHS setting contains "/tmp" - all tests will fail if this is not
the case.
"""
import pytest
import uuid

from pulp_smash.pulp3.bindings import (
    delete_orphans,
    monitor_task,
    monitor_task_group,
)
from pulp_smash.pulp3.utils import gen_repo

from pulpcore.client.pulp_container import ContainerRepositorySyncURL

from pulp_container.tests.functional.utils import gen_container_remote
from pulp_container.tests.functional.constants import REGISTRY_V2_REPO_PULP


def test_import_export_standard(
    container_remote_api,
    container_repository_api,
    container_repository_version_api,
    container_manifest_api,
    exporters_pulp_api_client,
    exporters_pulp_exports_api_client,
    importers_pulp_api_client,
    importers_pulp_imports_api_client,
    gen_object_with_cleanup,
):
    """Test exporting and importing of a container repository."""
    remote = container_remote_api.create(gen_container_remote())
    sync_data = ContainerRepositorySyncURL(remote=remote.pulp_href)
    repository = gen_object_with_cleanup(container_repository_api, gen_repo())
    sync_response = container_repository_api.sync(repository.pulp_href, sync_data)
    monitor_task(sync_response.task)

    # Export the repository
    body = {
        "name": str(uuid.uuid4()),
        "path": f"/tmp/{uuid.uuid4()}/",
        "repositories": [repository.pulp_href],
    }
    exporter = gen_object_with_cleanup(exporters_pulp_api_client, body)

    export_response = exporters_pulp_exports_api_client.create(exporter.pulp_href, {})
    export_href = monitor_task(export_response.task).created_resources[0]
    export = exporters_pulp_exports_api_client.read(export_href)

    # Clean the old repository out
    monitor_task(container_repository_version_api.delete(repository.latest_version_href).task)
    delete_orphans()

    # Import the repository
    import_repository = gen_object_with_cleanup(container_repository_api, gen_repo())

    body = {
        "name": str(uuid.uuid4()),
        "repo_mapping": {repository.name: import_repository.name},
    }
    importer = gen_object_with_cleanup(importers_pulp_api_client, body)

    filenames = [f for f in list(export.output_file_info.keys()) if f.endswith("tar.gz")]
    import_response = importers_pulp_imports_api_client.create(
        importer.pulp_href, {"path": filenames[0]}
    )
    if hasattr(import_response, "task_group"):
        task_group_href = import_response.task_group
    else:
        task_group_href = monitor_task(import_response.task).created_resources[1]
    monitor_task_group(task_group_href)

    # Verify that the imported repository contains the right associations
    import_repository = container_repository_api.read(import_repository.pulp_href)
    manifests = container_manifest_api.list(
        repository_version=import_repository.latest_version_href
    ).results

    for manifest in manifests:
        if "manifest.list" in manifest.media_type:
            assert manifest.listed_manifests != []
        else:
            assert manifest.blobs != []
            assert manifest.config_blob is not None


def test_import_export_create_repositories(
    registry_client,
    local_registry,
    container_distribution_api,
    container_repository_api,
    container_tag_api,
    container_manifest_api,
    exporters_pulp_api_client,
    exporters_pulp_exports_api_client,
    importers_pulp_api_client,
    importers_pulp_imports_api_client,
    gen_object_with_cleanup,
):
    """Test importing of a push repository without creating an initial repository manually."""
    if registry_client.name != "podman":
        pytest.skip("This test requires podman to push pulled content", allow_module_level=True)

    image_path = f"{REGISTRY_V2_REPO_PULP}:manifest_a"
    registry_client.pull(image_path)

    distribution_path = str(uuid.uuid4())
    local_registry.tag_and_push(image_path, f"{distribution_path}:manifest_a")

    distribution = container_distribution_api.list(name=distribution_path).results[0]

    body = {
        "name": str(uuid.uuid4()),
        "path": f"/tmp/{uuid.uuid4()}/",
        "repositories": [distribution.repository],
    }
    exporter = gen_object_with_cleanup(exporters_pulp_api_client, body)
    export_response = exporters_pulp_exports_api_client.create(exporter.pulp_href, {})
    export_href = monitor_task(export_response.task).created_resources[0]
    export = exporters_pulp_exports_api_client.read(export_href)

    # Clean the old repository out
    monitor_task(container_distribution_api.delete(distribution.pulp_href).task)
    delete_orphans()

    body = {"name": str(uuid.uuid4())}
    importer = gen_object_with_cleanup(importers_pulp_api_client, body)
    filenames = [f for f in list(export.output_file_info.keys()) if f.endswith("tar.gz")]

    import_response = importers_pulp_imports_api_client.create(
        importer.pulp_href, {"path": filenames[0], "create_repositories": True}
    )
    if hasattr(import_response, "task_group"):
        task_group_href = import_response.task_group
    else:
        task_group_href = monitor_task(import_response.task).created_resources[1]
    monitor_task_group(task_group_href)

    repositories = container_repository_api.list(name=distribution_path).results
    assert len(repositories) == 1

    tags = container_tag_api.list(
        name="manifest_a", repository_version=repositories[0].latest_version_href
    ).results
    assert len(tags) == 1

    manifests = container_manifest_api.list(
        repository_version=repositories[0].latest_version_href
    ).results

    for manifest in manifests:
        if "manifest.list" in manifest.media_type:
            assert manifest.listed_manifests != []
        else:
            assert manifest.blobs != []
            assert manifest.config_blob is not None

    monitor_task(container_repository_api.delete(repositories[0].pulp_href).task)
    delete_orphans()

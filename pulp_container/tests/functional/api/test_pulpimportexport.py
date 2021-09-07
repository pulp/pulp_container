"""
Tests PulpExporter and PulpImporter functionality

NOTE: assumes ALLOWED_EXPORT_PATHS setting contains "/tmp" - all tests will fail if this is not
the case.
"""
import unittest
from pulp_smash.utils import uuid4
from pulp_smash.pulp3.bindings import (
    delete_orphans,
    monitor_task,
    monitor_task_group,
)
from pulp_smash.pulp3.utils import gen_repo

from pulpcore.client.pulpcore import (
    ApiClient as CoreApiClient,
    ExportersPulpApi,
    ExportersPulpExportsApi,
    ImportersPulpApi,
    ImportersPulpImportsApi,
)

from pulpcore.client.pulp_container import (
    ApiClient as ContainerApiClient,
    ContentManifestsApi,
    RepositoriesContainerApi,
    RepositoriesContainerVersionsApi,
    RepositorySyncURL,
    RemotesContainerApi,
)
from pulp_container.tests.functional.utils import configuration, gen_container_remote


class PulpImportExportTestCase(unittest.TestCase):
    """
    Test exporting and importing of a container repository.
    """

    def test_import_export(self):
        """
        Test exporting and importing of a container repository.
        """
        core_client = CoreApiClient(configuration)
        container_client = ContainerApiClient(configuration)
        remotes_api = RemotesContainerApi(container_client)
        repositories_api = RepositoriesContainerApi(container_client)
        repository_versions_api = RepositoriesContainerVersionsApi(container_client)
        manifests_api = ContentManifestsApi(container_client)
        exporters_api = ExportersPulpApi(core_client)
        exports_api = ExportersPulpExportsApi(core_client)
        importers_api = ImportersPulpApi(core_client)
        imports_api = ImportersPulpImportsApi(core_client)

        # Setup
        remote = remotes_api.create(gen_container_remote())
        self.addCleanup(remotes_api.delete, remote.pulp_href)
        sync_data = RepositorySyncURL(remote=remote.pulp_href)
        repository = repositories_api.create(gen_repo())
        self.addCleanup(repositories_api.delete, repository.pulp_href)
        sync_response = repositories_api.sync(repository.pulp_href, sync_data)
        monitor_task(sync_response.task).created_resources

        # Export the repository
        body = {
            "name": uuid4(),
            "path": "/tmp/{}/".format(uuid4()),
            "repositories": [repository.pulp_href],
        }
        exporter = exporters_api.create(body)
        self.addCleanup(exporters_api.delete, exporter.pulp_href)

        export_response = exports_api.create(exporter.pulp_href, {})
        export_href = monitor_task(export_response.task).created_resources[0]
        export = exports_api.read(export_href)

        # Clean the old repository out
        monitor_task(repository_versions_api.delete(repository.latest_version_href).task)
        delete_orphans()

        # Import the repository
        import_repository = repositories_api.create(gen_repo())
        self.addCleanup(repositories_api.delete, import_repository.pulp_href)

        body = {
            "name": uuid4(),
            "repo_mapping": {repository.name: import_repository.name},
        }
        importer = importers_api.create(body)
        self.addCleanup(importers_api.delete, importer.pulp_href)

        filenames = [f for f in list(export.output_file_info.keys()) if f.endswith("tar.gz")]
        import_response = imports_api.create(importer.pulp_href, {"path": filenames[0]})
        task_group_href = monitor_task(import_response.task).created_resources[1]
        monitor_task_group(task_group_href)

        # Verify that the imported repository contains the right associations
        import_repository = repositories_api.read(import_repository.pulp_href)
        manifests = manifests_api.list(
            repository_version=import_repository.latest_version_href
        ).results

        for manifest in manifests:
            if "manifest.list" in manifest.media_type:
                self.assertNotEqual(manifest.listed_manifests, [])
            else:
                self.assertNotEqual(manifest.blobs, [])
                self.assertIsNotNone(manifest.config_blob)

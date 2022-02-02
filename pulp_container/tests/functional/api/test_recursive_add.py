# coding=utf-8
"""Tests that recursively add container content to repositories."""
from pulp_smash.pulp3.bindings import (
    delete_orphans,
    monitor_task,
    PulpTestCase,
)
from pulp_smash.pulp3.utils import gen_repo

from pulp_container.tests.functional.utils import (
    gen_container_remote,
    gen_container_client,
)
from pulp_container.tests.functional.constants import PULP_FIXTURE_1

from pulp_container.constants import MEDIA_TYPE

from pulpcore.client.pulp_container import (
    ApiException,
    ContainerContainerRemote,
    ContainerContainerRepository,
    ContentTagsApi,
    ContentManifestsApi,
    RemotesContainerApi,
    RepositoriesContainerApi,
    RepositoriesContainerVersionsApi,
    RepositorySyncURL,
)


class TestManifestCopy(PulpTestCase):
    """
    Test recursive copy of Manifests into a repository.

    This test targets the follow feature:
    https://pulp.plan.io/issues/3403
    """

    @classmethod
    def setUpClass(cls):
        """Sync pulp/test-fixture-1 so we can copy content from it."""
        api_client = gen_container_client()
        cls.repositories_api = RepositoriesContainerApi(api_client)
        cls.versions_api = RepositoriesContainerVersionsApi(api_client)
        cls.remotes_api = RemotesContainerApi(api_client)
        cls.tags_api = ContentTagsApi(api_client)
        cls.manifests_api = ContentManifestsApi(api_client)

        cls.from_repo = cls.repositories_api.create(ContainerContainerRepository(**gen_repo()))

        remote_data = gen_container_remote(upstream_name=PULP_FIXTURE_1)
        cls.remote = cls.remotes_api.create(ContainerContainerRemote(**remote_data))

        sync_data = RepositorySyncURL(remote=cls.remote.pulp_href)
        sync_response = cls.repositories_api.sync(cls.from_repo.pulp_href, sync_data)
        monitor_task(sync_response.task)

        cls.latest_from_version = cls.repositories_api.read(
            cls.from_repo.pulp_href
        ).latest_version_href

    def setUp(self):
        """Create an empty repository to copy into."""
        self.to_repo = self.repositories_api.create(ContainerContainerRepository(**gen_repo()))
        self.addCleanup(self.repositories_api.delete, self.to_repo.pulp_href)

    @classmethod
    def tearDownClass(cls):
        """Delete things made in setUpClass. addCleanup feature does not work with setupClass."""
        cls.repositories_api.delete(cls.from_repo.pulp_href)
        cls.repositories_api.delete(cls.remote.pulp_href)

    def test_missing_repository_argument(self):
        """Ensure source_repository or source_repository_version is required."""
        with self.assertRaises(ApiException) as context:
            self.repositories_api.copy_manifests(self.to_repo.pulp_href, {})
        self.assertEqual(context.exception.status, 400)

    def test_source_repository_and_source_version(self):
        """Passing source_repository_version and repository returns a 400."""
        with self.assertRaises(ApiException) as context:
            self.repositories_api.copy_manifests(
                self.to_repo.pulp_href,
                {
                    "source_repository": self.from_repo.pulp_href,
                    "source_repository_version": self.from_repo.latest_version_href,
                },
            )
        self.assertEqual(context.exception.status, 400)

    def test_copy_all_manifests(self):
        """Passing only source repository copies all manifests."""
        copy_response = self.repositories_api.copy_manifests(
            self.to_repo.pulp_href, {"source_repository": self.from_repo.pulp_href}
        )
        monitor_task(copy_response.task)

        latest_to = self.repositories_api.read(self.to_repo.pulp_href)
        latest_from = self.repositories_api.read(self.from_repo.pulp_href)
        to_repo_content = self.versions_api.read(
            latest_to.latest_version_href
        ).content_summary.present
        from_repo_content = self.versions_api.read(
            latest_from.latest_version_href
        ).content_summary.present
        for container_type in ["container.manifest", "container.blob"]:
            self.assertEqual(
                to_repo_content[container_type]["count"],
                from_repo_content[container_type]["count"],
                msg=container_type,
            )
        self.assertFalse("container.tag" in to_repo_content)

    def test_copy_all_manifests_from_version(self):
        """Passing only source version copies all manifests."""
        latest_from = self.repositories_api.read(self.from_repo.pulp_href)
        copy_response = self.repositories_api.copy_manifests(
            self.to_repo.pulp_href, {"source_repository_version": latest_from.latest_version_href}
        )
        monitor_task(copy_response.task)

        latest_to = self.repositories_api.read(self.to_repo.pulp_href)
        to_repo_content = self.versions_api.read(
            latest_to.latest_version_href
        ).content_summary.present
        from_repo_content = self.versions_api.read(
            latest_from.latest_version_href
        ).content_summary.present
        for container_type in ["container.manifest", "container.blob"]:
            self.assertEqual(
                to_repo_content[container_type]["count"],
                from_repo_content[container_type]["count"],
            )
        self.assertFalse("container.tag" in to_repo_content)

    def test_copy_manifest_by_digest(self):
        """Specify a single manifest by digest to copy."""
        manifest_a_href = (
            self.tags_api.list(name="manifest_a", repository_version=self.latest_from_version)
            .results[0]
            .tagged_manifest
        )
        manifest_a_digest = self.manifests_api.read(manifest_a_href).digest
        copy_response = self.repositories_api.copy_manifests(
            self.to_repo.pulp_href,
            {"source_repository": self.from_repo.pulp_href, "digests": [manifest_a_digest]},
        )
        monitor_task(copy_response.task)

        to_repo = self.repositories_api.read(self.to_repo.pulp_href)
        to_repo_content = self.versions_api.read(
            to_repo.latest_version_href
        ).content_summary.present
        self.assertFalse("container.tag" in to_repo_content)
        self.assertEqual(to_repo_content["container.manifest"]["count"], 1)
        # each manifest (non-list) has 3 blobs, 1 blob is shared
        self.assertEqual(to_repo_content["container.blob"]["count"], 3)

    def test_copy_manifest_by_digest_and_media_type(self):
        """Specify a single manifest by digest to copy."""
        manifest_a_href = (
            self.tags_api.list(name="manifest_a", repository_version=self.latest_from_version)
            .results[0]
            .tagged_manifest
        )
        manifest_a_digest = self.manifests_api.read(manifest_a_href).digest
        copy_response = self.repositories_api.copy_manifests(
            self.to_repo.pulp_href,
            {
                "source_repository": self.from_repo.pulp_href,
                "digests": [manifest_a_digest],
                "media_types": [MEDIA_TYPE.MANIFEST_V2],
            },
        )
        monitor_task(copy_response.task)

        to_repo = self.repositories_api.read(self.to_repo.pulp_href)
        to_repo_content = self.versions_api.read(
            to_repo.latest_version_href
        ).content_summary.present
        self.assertFalse("container.tag" in to_repo_content)
        self.assertEqual(to_repo_content["container.manifest"]["count"], 1)
        # manifest_a has 3 blobs
        # 3rd blob is the parent blob from apline repo
        self.assertEqual(to_repo_content["container.blob"]["count"], 3)

    def test_copy_all_manifest_lists_by_media_type(self):
        """Specify the media_type, to copy all manifest lists."""
        copy_response = self.repositories_api.copy_manifests(
            self.to_repo.pulp_href,
            {
                "source_repository": self.from_repo.pulp_href,
                "media_types": [MEDIA_TYPE.MANIFEST_LIST],
            },
        )
        monitor_task(copy_response.task)

        to_repo = self.repositories_api.read(self.to_repo.pulp_href)
        to_repo_content = self.versions_api.read(
            to_repo.latest_version_href
        ).content_summary.present
        self.assertFalse("container.tag" in to_repo_content)
        # Fixture has 4 manifest lists, which combined reference 5 manifests
        self.assertEqual(to_repo_content["container.manifest"]["count"], 9)
        # each manifest (non-list) has 3 blobs, 1 blob is shared
        # 11th blob is the parent blob from apline repo, which is shared by all other manifests
        self.assertEqual(to_repo_content["container.blob"]["count"], 11)

    def test_copy_all_manifests_by_media_type(self):
        """Specify the media_type, to copy all manifest lists."""
        copy_response = self.repositories_api.copy_manifests(
            self.to_repo.pulp_href,
            {
                "source_repository": self.from_repo.pulp_href,
                "media_types": [MEDIA_TYPE.MANIFEST_V1, MEDIA_TYPE.MANIFEST_V2],
            },
        )
        monitor_task(copy_response.task)

        to_repo = self.repositories_api.read(self.to_repo.pulp_href)
        to_repo_content = self.versions_api.read(
            to_repo.latest_version_href
        ).content_summary.present
        self.assertFalse("container.tag" in to_repo_content)
        # Fixture has 5 manifests that aren't manifest lists
        self.assertEqual(to_repo_content["container.manifest"]["count"], 5)
        # each manifest (non-list) has 3 blobs, 1 blob is shared
        # 11th blob is the parent blob from apline repo, which is shared by all other manifests
        self.assertEqual(to_repo_content["container.blob"]["count"], 11)

    def test_fail_to_copy_invalid_manifest_media_type(self):
        """Specify the media_type, to copy all manifest lists."""
        with self.assertRaises(ApiException) as context:
            self.repositories_api.copy_manifests(
                self.to_repo.pulp_href,
                {
                    "source_repository": self.from_repo.pulp_href,
                    "media_types": ["wrongwrongwrong"],
                },
            )
        self.assertEqual(context.exception.status, 400)

    def test_copy_by_digest_with_incorrect_media_type(self):
        """Ensure invalid media type will raise a 400."""
        ml_i_href = (
            self.tags_api.list(name="ml_i", repository_version=self.latest_from_version)
            .results[0]
            .tagged_manifest
        )
        ml_i_digest = self.manifests_api.read(ml_i_href).digest

        copy_response = self.repositories_api.copy_manifests(
            self.to_repo.pulp_href,
            {
                "source_repository": self.from_repo.pulp_href,
                "digests": [ml_i_digest],
                "media_types": [MEDIA_TYPE.MANIFEST_V2],
            },
        )
        monitor_task(copy_response.task)

        latest_to_repo_href = self.repositories_api.read(self.to_repo.pulp_href).latest_version_href
        # Assert no version created
        self.assertEqual(latest_to_repo_href, f"{self.to_repo.pulp_href}versions/0/")

    def test_copy_multiple_manifests_by_digest(self):
        """Specify digests to copy."""
        ml_i_href = (
            self.tags_api.list(name="ml_i", repository_version=self.latest_from_version)
            .results[0]
            .tagged_manifest
        )
        ml_i_digest = self.manifests_api.read(ml_i_href).digest

        ml_ii_href = (
            self.tags_api.list(name="ml_ii", repository_version=self.latest_from_version)
            .results[0]
            .tagged_manifest
        )
        ml_ii_digest = self.manifests_api.read(ml_ii_href).digest

        copy_response = self.repositories_api.copy_manifests(
            self.to_repo.pulp_href,
            {
                "source_repository": self.from_repo.pulp_href,
                "digests": [ml_i_digest, ml_ii_digest],
            },
        )
        monitor_task(copy_response.task)

        to_repo = self.repositories_api.read(self.to_repo.pulp_href)
        to_repo_content = self.versions_api.read(
            to_repo.latest_version_href
        ).content_summary.present
        self.assertFalse("container.tag" in to_repo_content)
        # each manifest list is a manifest and references 2 other manifests
        self.assertEqual(to_repo_content["container.manifest"]["count"], 6)
        # each manifest (non-list) has 3 blobs, 1 blob is shared
        # 9th blob is the parent blob from apline repo, which is shared by all other manifests
        self.assertEqual(to_repo_content["container.blob"]["count"], 9)

    def test_copy_manifests_by_digest_empty_list(self):
        """Passing an empty list copies no manifests."""
        self.repositories_api.copy_manifests(
            self.to_repo.pulp_href, {"source_repository": self.from_repo.pulp_href, "digests": []}
        )
        latest_to = self.repositories_api.read(self.to_repo.pulp_href)
        # Assert a new version was not created
        self.assertEqual(latest_to.latest_version_href, f"{self.to_repo.pulp_href}versions/0/")


class TestTagCopy(PulpTestCase):
    """Test recursive copy of tags content to a repository."""

    @classmethod
    def setUpClass(cls):
        """Sync pulp/test-fixture-1 so we can copy content from it."""
        api_client = gen_container_client()
        cls.repositories_api = RepositoriesContainerApi(api_client)
        cls.remotes_api = RemotesContainerApi(api_client)
        cls.versions_api = RepositoriesContainerVersionsApi(api_client)
        cls.tags_api = ContentTagsApi(api_client)
        cls.manifests_api = ContentManifestsApi(api_client)

        repository_data = ContainerContainerRepository(**gen_repo())
        cls.from_repo = cls.repositories_api.create(repository_data)

        remote_data = gen_container_remote(upstream_name=PULP_FIXTURE_1)
        cls.remote = cls.remotes_api.create(ContainerContainerRemote(**remote_data))

        sync_data = RepositorySyncURL(remote=cls.remote.pulp_href)
        sync_response = cls.repositories_api.sync(cls.from_repo.pulp_href, sync_data)
        monitor_task(sync_response.task)

        cls.latest_from_version = cls.repositories_api.read(
            cls.from_repo.pulp_href
        ).latest_version_href

    def setUp(self):
        """Create an empty repository to copy into."""
        self.to_repo = self.repositories_api.create(gen_repo())
        self.addCleanup(self.repositories_api.delete, self.to_repo.pulp_href)

    @classmethod
    def tearDownClass(cls):
        """Delete things made in setUpClass. addCleanup feature does not work with setupClass."""
        cls.repositories_api.delete(cls.from_repo.pulp_href)
        cls.remotes_api.delete(cls.remote.pulp_href)

    def test_missing_repository_argument(self):
        """Ensure source_repository or source_repository_version is required."""
        with self.assertRaises(ApiException):
            self.repositories_api.copy_tags(self.to_repo.pulp_href, {})

    def test_source_repository_and_source_version(self):
        """Passing both source_repository_version and source_repository returns a 400."""
        with self.assertRaises(ApiException) as context:
            self.repositories_api.copy_tags(
                self.to_repo.pulp_href,
                {
                    "source_repository": self.from_repo.pulp_href,
                    "source_repository_version": self.from_repo.latest_version_href,
                },
            )
        self.assertEqual(context.exception.status, 400)

    def test_copy_all_tags(self):
        """Passing only source and destination repositories copies all tags."""
        copy_response = self.repositories_api.copy_tags(
            self.to_repo.pulp_href, {"source_repository": self.from_repo.pulp_href}
        )
        monitor_task(copy_response.task)

        to_repo = self.repositories_api.read(self.to_repo.pulp_href)
        from_repo = self.repositories_api.read(self.from_repo.pulp_href)
        to_repo_content = self.versions_api.read(
            to_repo.latest_version_href
        ).content_summary.present
        from_repo_content = self.versions_api.read(
            from_repo.latest_version_href
        ).content_summary.present
        for container_type in ["container.tag", "container.manifest", "container.blob"]:
            self.assertEqual(
                to_repo_content[container_type]["count"],
                from_repo_content[container_type]["count"],
                msg=container_type,
            )

    def test_copy_all_tags_from_version(self):
        """Passing only source version and destination repositories copies all tags."""
        latest_from_repo_href = self.repositories_api.read(
            self.from_repo.pulp_href
        ).latest_version_href
        copy_response = self.repositories_api.copy_tags(
            self.to_repo.pulp_href, {"source_repository_version": latest_from_repo_href}
        )
        monitor_task(copy_response.task)

        to_repo = self.repositories_api.read(self.to_repo.pulp_href)
        to_repo_content = self.versions_api.read(
            to_repo.latest_version_href
        ).content_summary.present
        from_repo_content = self.versions_api.read(latest_from_repo_href).content_summary.present
        for container_type in ["container.tag", "container.manifest", "container.blob"]:
            self.assertEqual(
                to_repo_content[container_type]["count"],
                from_repo_content[container_type]["count"],
                msg=container_type,
            )

    def test_copy_tags_by_name(self):
        """Copy tags in destination repo that match name."""
        copy_response = self.repositories_api.copy_tags(
            self.to_repo.pulp_href,
            {"source_repository": self.from_repo.pulp_href, "names": ["ml_i", "manifest_c"]},
        )
        monitor_task(copy_response.task)

        to_repo = self.repositories_api.read(self.to_repo.pulp_href)
        to_repo_content = self.versions_api.read(
            to_repo.latest_version_href
        ).content_summary.present
        self.assertEqual(to_repo_content["container.tag"]["count"], 2)
        # ml_i has 1 manifest list, 2 manifests, manifest_c has 1 manifest
        self.assertEqual(to_repo_content["container.manifest"]["count"], 4)
        # each manifest (non-list) has 3 blobs, 1 blob is shared
        # 7th blob is the parent blob from apline repo, which is shared by all other manifests
        self.assertEqual(to_repo_content["container.blob"]["count"], 7)

    def test_copy_tags_by_name_empty_list(self):
        """Passing an empty list of names copies nothing."""
        copy_response = self.repositories_api.copy_tags(
            self.to_repo.pulp_href, {"source_repository": self.from_repo.pulp_href, "names": []}
        )
        monitor_task(copy_response.task)

        latest_to_repo_href = self.repositories_api.read(self.to_repo.pulp_href).latest_version_href
        # Assert a new version was not created
        self.assertEqual(latest_to_repo_href, f"{self.to_repo.pulp_href}versions/0/")

    def test_copy_tags_with_conflicting_names(self):
        """If tag names are already present in a repository, the conflicting tags are removed."""
        copy_response = self.repositories_api.copy_tags(
            self.to_repo.pulp_href, {"source_repository": self.from_repo.pulp_href}
        )
        monitor_task(copy_response.task)
        # Tag the 'manifest_b' manifest as 'manifest_a'
        latest_version_href = self.repositories_api.read(self.to_repo.pulp_href).latest_version_href
        manifest_b_href = (
            self.tags_api.list(name="manifest_b", repository_version=latest_version_href)
            .results[0]
            .tagged_manifest
        )
        manifest_b = self.manifests_api.read(manifest_b_href)
        params = {"tag": "manifest_a", "digest": manifest_b.digest}
        tag_response = self.repositories_api.tag(self.to_repo.pulp_href, params)
        monitor_task(tag_response.task)
        # Copy tags again from the original repo
        copy_response = self.repositories_api.copy_tags(
            self.to_repo.pulp_href, {"source_repository": self.from_repo.pulp_href}
        )
        monitor_task(copy_response.task)
        to_repo = self.repositories_api.read(self.to_repo.pulp_href)
        from_repo = self.repositories_api.read(self.from_repo.pulp_href)
        to_repo_content = self.versions_api.read(to_repo.latest_version_href).content_summary
        from_repo_content = self.versions_api.read(from_repo.latest_version_href).content_summary
        for container_type in ["container.tag", "container.manifest", "container.blob"]:
            self.assertEqual(
                to_repo_content.present[container_type]["count"],
                from_repo_content.present[container_type]["count"],
            )

        self.assertEqual(to_repo_content.added["container.tag"]["count"], 1)
        self.assertEqual(to_repo_content.removed["container.tag"]["count"], 1)


class TestRecursiveAdd(PulpTestCase):
    """Test recursively adding container content to a repository."""

    @classmethod
    def setUpClass(cls):
        """Sync pulp/test-fixture-1 so we can copy content from it."""
        api_client = gen_container_client()
        cls.repositories_api = RepositoriesContainerApi(api_client)
        cls.remotes_api = RemotesContainerApi(api_client)
        cls.tags_api = ContentTagsApi(api_client)
        cls.versions_api = RepositoriesContainerVersionsApi(api_client)
        cls.manifests_api = ContentManifestsApi(api_client)

        repository_data = ContainerContainerRepository(**gen_repo())
        cls.from_repo = cls.repositories_api.create(repository_data)

        remote_data = gen_container_remote(upstream_name=PULP_FIXTURE_1)
        cls.remote = cls.remotes_api.create(ContainerContainerRemote(**remote_data))

        sync_data = RepositorySyncURL(remote=cls.remote.pulp_href)
        sync_response = cls.repositories_api.sync(cls.from_repo.pulp_href, sync_data)
        monitor_task(sync_response.task)

        cls.latest_from_version = cls.repositories_api.read(
            cls.from_repo.pulp_href
        ).latest_version_href

    def setUp(self):
        """Create an empty repository to copy into."""
        self.to_repo = self.repositories_api.create(gen_repo())
        self.addCleanup(self.repositories_api.delete, self.to_repo.pulp_href)

    @classmethod
    def tearDownClass(cls):
        """Delete things made in setUpClass. addCleanup feature does not work with setupClass."""
        cls.repositories_api.delete(cls.from_repo.pulp_href)
        cls.remotes_api.delete(cls.remote.pulp_href)
        delete_orphans()

    def test_repository_only(self):
        """Passing only a repository does not create a new version."""
        add_response = self.repositories_api.add(self.to_repo.pulp_href, {})
        monitor_task(add_response.task)

        latest_version_href = self.repositories_api.read(self.to_repo.pulp_href).latest_version_href
        self.assertEqual(latest_version_href, self.to_repo.latest_version_href)

    def test_manifest_recursion(self):
        """Add a manifest and its related blobs."""
        manifest_a = (
            self.tags_api.list(name="manifest_a", repository_version=self.latest_from_version)
            .results[0]
            .tagged_manifest
        )
        add_response = self.repositories_api.add(
            self.to_repo.pulp_href, {"content_units": [manifest_a]}
        )
        monitor_task(add_response.task)
        latest_version_href = self.repositories_api.read(self.to_repo.pulp_href).latest_version_href
        latest = self.versions_api.read(latest_version_href)

        # No tags added
        self.assertFalse("container.manifest-tag" in latest.content_summary.added)

        # each manifest (non-list) has 3 blobs, 1 blob is shared
        self.assertEqual(latest.content_summary.added["container.manifest"]["count"], 1)
        self.assertEqual(latest.content_summary.added["container.blob"]["count"], 3)

    def test_manifest_list_recursion(self):
        """Add a Manifest List, related manifests, and related blobs."""
        ml_i = (
            self.tags_api.list(name="ml_i", repository_version=self.latest_from_version)
            .results[0]
            .tagged_manifest
        )
        add_response = self.repositories_api.add(self.to_repo.pulp_href, {"content_units": [ml_i]})
        monitor_task(add_response.task)

        latest_version_href = self.repositories_api.read(self.to_repo.pulp_href).latest_version_href
        latest = self.versions_api.read(latest_version_href)

        # No tags added
        self.assertFalse("container.tag" in latest.content_summary.added)
        # 1 manifest list 2 manifests
        self.assertEqual(latest.content_summary.added["container.manifest"]["count"], 3)

    def test_tagged_manifest_list_recursion(self):
        """Add a tagged manifest list, and its related manifests and blobs."""
        ml_i_tag = (
            self.tags_api.list(name="ml_i", repository_version=self.latest_from_version)
            .results[0]
            .pulp_href
        )
        add_response = self.repositories_api.add(
            self.to_repo.pulp_href, {"content_units": [ml_i_tag]}
        )
        monitor_task(add_response.task)
        latest_version_href = self.repositories_api.read(self.to_repo.pulp_href).latest_version_href
        latest = self.versions_api.read(latest_version_href)
        self.assertEqual(latest.content_summary.added["container.tag"]["count"], 1)
        # 1 manifest list 2 manifests
        self.assertEqual(latest.content_summary.added["container.manifest"]["count"], 3)
        # each manifest (non-list) has 3 blobs, 1 blob is shared
        # 5th blob is the parent blob from apline repo, which is shared by all other manifests
        self.assertEqual(latest.content_summary.added["container.blob"]["count"], 5)

    def test_tagged_manifest_recursion(self):
        """Add a tagged manifest and its related blobs."""
        manifest_a_tag = (
            self.tags_api.list(name="manifest_a", repository_version=self.latest_from_version)
            .results[0]
            .pulp_href
        )
        add_response = self.repositories_api.add(
            self.to_repo.pulp_href, {"content_units": [manifest_a_tag]}
        )
        monitor_task(add_response.task)
        latest_version_href = self.repositories_api.read(self.to_repo.pulp_href).latest_version_href
        latest = self.versions_api.read(latest_version_href)

        self.assertEqual(latest.content_summary.added["container.tag"]["count"], 1)
        self.assertEqual(latest.content_summary.added["container.manifest"]["count"], 1)
        self.assertEqual(latest.content_summary.added["container.blob"]["count"], 3)

    def test_tag_replacement(self):
        """Add a tagged manifest to a repo with a tag of that name already in place."""
        manifest_a_tag = (
            self.tags_api.list(name="manifest_a", repository_version=self.latest_from_version)
            .results[0]
            .pulp_href
        )

        # Add manifest_b to the repo
        manifest_b = (
            self.tags_api.list(name="manifest_b", repository_version=self.latest_from_version)
            .results[0]
            .tagged_manifest
        )
        manifest_b_digest = self.manifests_api.read(manifest_b).digest
        add_response = self.repositories_api.add(
            self.to_repo.pulp_href, {"content_units": [manifest_b]}
        )
        monitor_task(add_response.task)
        # Tag manifest_b as `manifest_a`
        params = {"tag": "manifest_a", "digest": manifest_b_digest}
        self.repositories_api.tag(self.to_repo.pulp_href, params)

        # Now add original manifest_a tag to the repo, which should remove the
        # new manifest_a tag, but leave the tagged manifest (manifest_b)
        add_response = self.repositories_api.add(
            self.to_repo.pulp_href, {"content_units": [manifest_a_tag]}
        )
        monitor_task(add_response.task)

        latest_version_href = self.repositories_api.read(self.to_repo.pulp_href).latest_version_href
        latest = self.versions_api.read(latest_version_href)
        self.assertEqual(latest.content_summary.added["container.tag"]["count"], 1)
        self.assertEqual(latest.content_summary.removed["container.tag"]["count"], 1)
        self.assertFalse("container.manifest" in latest.content_summary.removed)
        self.assertFalse("container.blob" in latest.content_summary.removed)

    def test_many_tagged_manifest_lists(self):
        """Add several Manifest List, related manifests, and related blobs."""
        ml_i_tag = (
            self.tags_api.list(name="ml_i", repository_version=self.latest_from_version)
            .results[0]
            .pulp_href
        )
        ml_ii_tag = (
            self.tags_api.list(name="ml_ii", repository_version=self.latest_from_version)
            .results[0]
            .pulp_href
        )
        ml_iii_tag = (
            self.tags_api.list(name="ml_iii", repository_version=self.latest_from_version)
            .results[0]
            .pulp_href
        )
        ml_iv_tag = (
            self.tags_api.list(name="ml_iv", repository_version=self.latest_from_version)
            .results[0]
            .pulp_href
        )
        add_response = self.repositories_api.add(
            self.to_repo.pulp_href, {"content_units": [ml_i_tag, ml_ii_tag, ml_iii_tag, ml_iv_tag]}
        )
        monitor_task(add_response.task)

        latest_version_href = self.repositories_api.read(self.to_repo.pulp_href).latest_version_href
        latest = self.versions_api.read(latest_version_href)

        self.assertEqual(latest.content_summary.added["container.tag"]["count"], 4)
        self.assertEqual(latest.content_summary.added["container.manifest"]["count"], 9)
        self.assertEqual(latest.content_summary.added["container.blob"]["count"], 11)

"""Tests related to the Redis content caching."""

import os
import requests
import unittest
from urllib.parse import urljoin

from pulp_smash import cli, config, utils
from pulp_smash.pulp3.bindings import delete_orphans, monitor_task
from pulp_smash.pulp3.utils import gen_distribution, gen_repo

from pulpcore.client.pulp_container import (
    ContainerRepositorySyncURL,
    ContentBlobsApi,
    ContentManifestsApi,
    ContentTagsApi,
    DistributionsContainerApi,
    RepositoriesContainerApi,
    RemotesContainerApi,
    PatchedcontainerContainerDistribution,
    UnTagImage,
)

from pulp_container.tests.functional.utils import (
    gen_container_client,
    gen_container_remote,
    get_auth_for_url,
)


from pulp_container.constants import MEDIA_TYPE

STANDARD_FILE_STORAGE_FRAMEWORKS = [
    "django.core.files.storage.FileSystemStorage",
    "pulpcore.app.models.storage.FileSystem",
]

cli_client = cli.Client(config.get_config())
DEFAULT_FILE_STORAGE = utils.get_pulp_setting(cli_client, "DEFAULT_FILE_STORAGE")
CACHE_ENABLED = utils.get_pulp_setting(cli_client, "CACHE_ENABLED")

PULP_CONTENT_HOST_BASE_URL = config.get_config().get_base_url()


@unittest.skipUnless(CACHE_ENABLED, "The caching machinery was not enabled")
class ContentCacheTestCache(unittest.TestCase):
    """A test case that verifies the functionality of the Redis caching machinery."""

    @classmethod
    def setUpClass(cls):
        """Sync a remote repository and create a new distribution pointing to the repository."""
        client_api = gen_container_client()
        cls.blobs_api = ContentBlobsApi(client_api)
        cls.manifests_api = ContentManifestsApi(client_api)
        cls.tags_api = ContentTagsApi(client_api)
        cls.repo_api = RepositoriesContainerApi(client_api)
        cls.remote_api = RemotesContainerApi(client_api)
        cls.dist_api = DistributionsContainerApi(client_api)

        cls.repo = cls.repo_api.create(gen_repo())
        cls.remote = cls.remote_api.create(gen_container_remote())
        body = ContainerRepositorySyncURL(remote=cls.remote.pulp_href)
        response = cls.repo_api.sync(cls.repo.pulp_href, body)
        monitor_task(response.task)

        cls.repo = cls.repo_api.read(cls.repo.pulp_href)

        response = cls.dist_api.create(gen_distribution(repository=cls.repo.pulp_href))
        cls.distro = cls.dist_api.read(monitor_task(response.task).created_resources[0])

        relative_path = os.path.join("v2/", f"{cls.distro.base_path}/")
        cls.dist_url = urljoin(PULP_CONTENT_HOST_BASE_URL, relative_path)

        delete_orphans()

    @classmethod
    def tearDownClass(cls):
        """Remove the created distribution, remote, and repository."""
        cls.dist_api.delete(cls.distro.pulp_href)
        cls.remote_api.delete(cls.remote.pulp_href)

        delete_orphans()

    def test_01_basic_cache_access(self):
        """Test whether responses are cached for initial querying."""
        self.check_content(cache_status_first_func)

    def test_02_remove_repository_invalidates(self):
        """Test if removing the repository from the distribution invalidates the cache."""
        body = PatchedcontainerContainerDistribution(repository="")
        response = self.dist_api.partial_update(self.distro.pulp_href, body)
        monitor_task(response.task)

        self.check_content(cache_status_not_found_func)

    def test_03_restore_repository(self):
        """Test if responses are cacheable when the repository is added back."""
        body = PatchedcontainerContainerDistribution(repository=self.repo.pulp_href)
        response = self.dist_api.partial_update(self.distro.pulp_href, body)
        monitor_task(response.task)

        self.check_content(cache_status_first_func)

    def test_04_multiple_distributions(self):
        """Add a new distribution and check if its responses are cached separately."""
        response = self.dist_api.create(gen_distribution(repository=self.repo.pulp_href))
        distro2_pulp_url = monitor_task(response.task).created_resources[0]
        self.__class__.distro2 = self.dist_api.read(distro2_pulp_url)

        relative_path = os.path.join("v2/", f"{self.distro2.base_path}/")
        self.__class__.dist_url2 = urljoin(PULP_CONTENT_HOST_BASE_URL, relative_path)

        self.check_content(cache_status_found_func)
        self.check_content(cache_status_first_func, dist_url=self.dist_url2)

    def test_05_different_headers(self):
        """Simulate a scenario where a user queries manifests with different Accept headers."""
        self.check_content(cache_status_found_func)
        self.check_content(
            cache_status_first_func,
            headers={"Accept": f"{MEDIA_TYPE.INDEX_OCI},{MEDIA_TYPE.MANIFEST_LIST}"},
        )

    def test_06_invalidate_multiple_distributions(self):
        """Test if updating the repository referenced by multiple distributions invalidates all."""
        untag_data = UnTagImage(tag="linux")
        response = self.repo_api.untag(self.repo.pulp_href, untag_data)
        monitor_task(response.task)

        self.check_content(cache_status_first_func)
        self.check_content(cache_status_first_func, dist_url=self.dist_url2)

    def test_07_delete_distribution_invalidates_one(self):
        """Test that deleting one distribution sharing the repository only invalidates its cache."""
        response = self.dist_api.delete(self.distro2.pulp_href)
        monitor_task(response.task)

        self.check_content(cache_status_found_func)
        self.check_content(cache_status_not_found_func, dist_url=self.dist_url2)

    def test_08_delete_repo_invalidates(self):
        """Tests that deleting the repository invalidates the cache."""
        response = self.repo_api.delete(self.repo.pulp_href)
        monitor_task(response.task)
        self.check_content(cache_status_not_found_func)

    def test_09_no_error_when_accessing_invalid_file(self):
        """Tests that accessing content, that does not exist, gives an HTTP 404 error."""
        files = ["invalid", "another/bad-one", "DNE/"]
        for f in files:
            url = urljoin(self.dist_url, f)
            response = requests.get(url)

            response_metadata = self.fetch_response_metadata(response)
            self.assertEqual(cache_status_not_found_func(0), response_metadata, url)

    def check_content(self, expect_metadata, tag_name="latest", dist_url=None, headers=None):
        """Check a manifest and blob referenced by the passed tag with the expected assertions."""
        latest_tag = self.tags_api.list(name=tag_name).to_dict()["results"][0]
        manifest_by_tag = f"manifests/{tag_name}"

        latest_manifest = self.manifests_api.read(latest_tag["tagged_manifest"])
        manifest_by_digest = f"manifests/{latest_manifest.digest}"

        sorted_manifests = sorted(latest_manifest.listed_manifests)
        first_listed_manifest = self.manifests_api.read(sorted_manifests[0])
        sorted_blobs = sorted(first_listed_manifest.blobs)
        latest_first_blob = self.blobs_api.read(sorted_blobs[0])
        blob_by_digest = f"blobs/{latest_first_blob.digest}"

        headers = headers if headers else {"Accept": latest_manifest.media_type}

        duplicated_content_units = sorted([manifest_by_tag, manifest_by_digest] * 2)
        for i, c in enumerate(duplicated_content_units):
            url = urljoin(dist_url or self.dist_url, c)
            self.check_cache(url, expect_metadata(i), headers)

        duplicated_content_units = [blob_by_digest] * 2
        for i, c in enumerate(duplicated_content_units):
            url = urljoin(dist_url or self.dist_url, c)
            self.check_cache(url, expect_metadata(i), headers)

    def check_cache(self, url, expected_metadata, headers):
        """A helper function to check if cache miss or hit occurred."""
        auth = get_auth_for_url(url)

        response = requests.get(url, auth=auth, headers=headers)
        response_metadata = self.fetch_response_metadata(response)
        self.assertEqual(expected_metadata, response_metadata, url)

    def fetch_response_metadata(self, response):
        """Retrieve metadata from the passed response and normalize status code for redirects."""
        if DEFAULT_FILE_STORAGE in STANDARD_FILE_STORAGE_FRAMEWORKS:
            return response.status_code, response.headers.get("X-PULP-CACHE")
        else:
            if response.history:
                response = response.history[0]
                response.status_code = 200
            return response.status_code, response.headers.get("X-PULP-CACHE")


def cache_status_first_func(i):
    """Miss at first, then hit."""
    return 200, "HIT" if i % 2 == 1 else "MISS"


def cache_status_found_func(_):
    """Hit all the time."""
    return 200, "HIT"


def cache_status_not_found_func(_):
    """End with does not exist."""
    return 404, None

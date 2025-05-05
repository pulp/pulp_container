"""Tests related to the Redis content caching."""

import pytest
import requests
from urllib.parse import urljoin

from pulp_container.tests.functional.utils import get_auth_for_url
from pulp_container.constants import MEDIA_TYPE


@pytest.fixture
def check_content(container_bindings, bindings_cfg):
    """Check a manifest and blob referenced by the passed tag with the expected assertions."""

    def _check_content(expect_metadata, dist_url, tag_name="latest", headers=None):
        latest_tag = container_bindings.ContentTagsApi.list(name=tag_name).results[0]
        manifest_by_tag = f"manifests/{tag_name}"

        latest_manifest = container_bindings.ContentManifestsApi.read(latest_tag.tagged_manifest)
        manifest_by_digest = f"manifests/{latest_manifest.digest}"

        sorted_manifests = sorted(latest_manifest.listed_manifests)
        first_listed_manifest = container_bindings.ContentManifestsApi.read(sorted_manifests[0])
        sorted_blobs = sorted(first_listed_manifest.blobs)
        latest_first_blob = container_bindings.ContentBlobsApi.read(sorted_blobs[0])
        blob_by_digest = f"blobs/{latest_first_blob.digest}"

        headers = headers if headers else {"Accept": latest_manifest.media_type}
        auth = (bindings_cfg.username, bindings_cfg.password)

        duplicated_content_units = sorted([manifest_by_tag, manifest_by_digest] * 2)
        for i, c in enumerate(duplicated_content_units):
            url = urljoin(dist_url, c)
            check_cache(url, expect_metadata(i), headers, auth, MEDIA_TYPE.MANIFEST_LIST)

        duplicated_content_units = [blob_by_digest] * 2
        for i, c in enumerate(duplicated_content_units):
            url = urljoin(dist_url, c)
            check_cache(url, expect_metadata(i), headers, auth, "application/octet-stream")

    return _check_content


def check_cache(url, expected_metadata, headers, auth, content_type):
    """A helper function to check if cache miss or hit occurred."""
    auth = get_auth_for_url(url, auth=auth)

    response = requests.get(url, auth=auth, headers=headers)
    response_metadata = fetch_response_metadata(response)
    assert expected_metadata == response_metadata, url
    # Check that we return the correct content type for both cache hits and misses
    if response.status_code == 200:
        assert response.headers.get("Content-Type") == content_type, url


def fetch_response_metadata(response):
    """Retrieve metadata from the passed response and normalize status code for redirects."""
    if response.history:
        response = response.history[0]
        response.status_code = 200
    return response.status_code, response.headers.get("X-PULP-CACHE")


# @pytest.mark.parallel  # Some other parallel test is causing this fail periodically
def test_content_cache(
    container_bindings,
    container_repository_factory,
    container_remote_factory,
    container_distribution_factory,
    container_sync,
    check_content,
    full_path,
    bindings_cfg,
    pulp_settings,
    monitor_task,
):
    """A test case that verifies the functionality of the Redis caching machinery."""
    if not pulp_settings.get("CACHE_ENABLED"):
        pytest.skip("The caching machinery was not enabled")

    repo = container_repository_factory()
    remote = container_remote_factory()
    container_sync(repo, remote)
    repo = container_bindings.RepositoriesContainerApi.read(repo.pulp_href)
    distribution = container_distribution_factory(repository=repo.pulp_href)
    dist_url = urljoin(bindings_cfg.host, f"v2/{full_path(distribution)}/")

    # Test whether responses are cached for initial querying.
    check_content(cache_status_first_func, dist_url)

    # Test if removing the repository from the distribution invalidates the cache.
    body = {"repository": ""}
    response = container_bindings.DistributionsContainerApi.partial_update(
        distribution.pulp_href, body
    )
    monitor_task(response.task)

    check_content(cache_status_not_found_func, dist_url)

    # Test if responses are cacheable when the repository is added back.
    body = {"repository": repo.pulp_href}
    response = container_bindings.DistributionsContainerApi.partial_update(
        distribution.pulp_href, body
    )
    monitor_task(response.task)

    check_content(cache_status_first_func, dist_url)

    # Add a new distribution and check if its responses are cached separately.
    distro2 = container_distribution_factory(repository=repo.pulp_href)
    dist_url2 = urljoin(bindings_cfg.host, f"v2/{full_path(distro2)}/")

    check_content(cache_status_found_func, dist_url)
    check_content(cache_status_first_func, dist_url=dist_url2)

    # Simulate a scenario where a user queries manifests with different Accept headers.
    check_content(cache_status_found_func, dist_url)
    check_content(
        cache_status_first_func,
        dist_url,
        headers={"Accept": f"{MEDIA_TYPE.INDEX_OCI},{MEDIA_TYPE.MANIFEST_LIST}"},
    )

    # Test if updating the repository referenced by multiple distributions invalidates all.
    untag_data = {"tag": "linux"}
    response = container_bindings.RepositoriesContainerApi.untag(repo.pulp_href, untag_data)
    monitor_task(response.task)

    check_content(cache_status_first_func, dist_url)
    check_content(cache_status_first_func, dist_url=dist_url2)

    # Test that deleting one distribution sharing the repository only invalidates its cache.
    response = container_bindings.DistributionsContainerApi.delete(distro2.pulp_href)
    monitor_task(response.task)

    check_content(cache_status_found_func, dist_url)
    check_content(cache_status_not_found_func, dist_url=dist_url2)

    # Tests that deleting the repository invalidates the cache.
    response = container_bindings.RepositoriesContainerApi.delete(repo.pulp_href)
    monitor_task(response.task)
    check_content(cache_status_not_found_func, dist_url)

    # Tests that accessing content, that does not exist, gives an HTTP 404 error.
    files = ["invalid", "another/bad-one", "DNE/"]
    for f in files:
        url = urljoin(dist_url, f)
        response = requests.get(url)

        response_metadata = fetch_response_metadata(response)
        assert cache_status_not_found_func(0) == response_metadata, url


def cache_status_first_func(i):
    """Miss at first, then hit."""
    return 200, "HIT" if i % 2 == 1 else "MISS"


def cache_status_found_func(_):
    """Hit all the time."""
    return 200, "HIT"


def cache_status_not_found_func(_):
    """End with does not exist."""
    return 404, None

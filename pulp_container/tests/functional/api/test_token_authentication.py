"""Tests for token authentication."""

import pytest
import aiohttp
import asyncio

from urllib.parse import urljoin
import requests

from pulp_container.tests.functional.utils import (
    get_auth_for_url,
)
from pulp_container.constants import MEDIA_TYPE
from pulp_container.tests.functional.constants import PULP_FIXTURE_1


class TestTokenAuthentication:
    """
    A test case for authenticating users via Bearer token.

    This tests targets the following issue:

    * `Pulp #4938 <https://pulp.plan.io/issues/4938>`_
    """

    @pytest.fixture(scope="class")
    def setup(
        self,
        container_repository_factory,
        container_remote_factory,
        container_sync,
        container_distribution_factory,
        container_bindings,
    ):
        container_repo = container_repository_factory()
        container_remote = container_remote_factory(upstream_name=PULP_FIXTURE_1)
        container_sync(container_repo, container_remote)
        distro = container_distribution_factory(repository=container_repo.pulp_href)
        tag_response = container_bindings.ContentTagsApi.list(name="manifest_a")
        tagged_manifest_href = tag_response.results[0].tagged_manifest
        manifest = container_bindings.ContentManifestsApi.read(tagged_manifest_href)
        config_blob = container_bindings.ContentBlobsApi.read(manifest.config_blob)
        return distro, config_blob

    def test_pull_image_with_raw_http_requests(self, setup, full_path, bindings_cfg):
        """
        Test if a content was pulled from a registry by using raw HTTP requests.

        The registry offers a reference to a certified authority which generates a
        Bearer token. The generated Bearer token is afterwards used to pull the image.
        All requests are sent via aiohttp modules.
        """
        distro, config_blob = setup
        image_path = f"/v2/{full_path(distro)}/manifests/manifest_a"
        latest_image_url = urljoin(bindings_cfg.host, image_path)

        auth = get_auth_for_url(latest_image_url)
        content_response = requests.get(
            latest_image_url, auth=auth, headers={"Accept": MEDIA_TYPE.MANIFEST_V2}
        )
        content_response.raise_for_status()
        assert content_response.json()["config"]["digest"] == config_blob.digest

    def test_pull_image_with_real_container_client(self, setup, local_registry, full_path):
        """
        Test if a CLI client is able to pull an image from an authenticated registry.

        This test checks if ordinary clients, like docker, or podman, are able to pull the
        image from a secured registry.
        """
        distro, config_blob = setup
        image_with_tag = full_path(f"{distro.base_path}:manifest_a")

        local_registry.pull(image_with_tag)

        image = local_registry.inspect(image_with_tag)

        # The docker client returns a different Id compared to an Id returned by the podman client.
        # 'Id': 'sha256:d21d863f69b5de1a973a41344488f2ec89a625f2624195f51b4e2d54a97fc53b' (docker)
        # 'Id': 'd21d863f69b5de1a973a41344488f2ec89a625f2624195f51b4e2d54a97fc53b' (podman)
        # As long as the output differs in this manner, it is necessary to prepend the string
        # 'sha256:' to the fetched digest.
        image_id = image[0]["Id"]
        if image_id.startswith("sha256:"):
            image_digest = image_id
        else:
            image_digest = "sha256:" + image_id

        assert image_digest == config_blob.digest


def test_invalid_user(pulp_settings, local_registry):
    """Test if the token server correctly returns a 401 error in case of invalid credentials."""

    async def get_token():
        url = f"{pulp_settings.TOKEN_SERVER}?service={local_registry.name}"
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, auth=aiohttp.BasicAuth("test", "invalid"), ssl=False
            ) as response:
                return response.status

    status = asyncio.run(get_token())
    assert status == 401

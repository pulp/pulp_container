"""Unit tests for HEAD-based manifest version checking in pull-through caching."""

import unittest
from unittest.mock import MagicMock, patch

from aiohttp.client_exceptions import ClientConnectionError, ClientResponseError
from rest_framework.exceptions import Throttled

from pulp_container.app.exceptions import BadGateway, GatewayTimeout, ManifestNotFound
from pulp_container.app.registry_api import Manifests
from pulpcore.plugin.exceptions import TimeoutException


def _mock_response(digest):
    response = MagicMock()
    response.headers = {"docker-content-digest": digest} if digest else {}
    return response


class TestFetchManifest(unittest.TestCase):
    """Exercise the HEAD-first manifest resolution flow."""

    def setUp(self):
        self.view = Manifests()
        self.remote = MagicMock()
        self.remote.namespaced_upstream_name = "library/test"
        self.remote.url = "https://registry.example/"

    def _set_downloaders(self, *downloaders):
        self.remote.get_downloader = MagicMock(side_effect=list(downloaders))

    @patch("pulp_container.app.registry_api.get_domain")
    @patch("pulp_container.app.registry_api.models.Manifest.objects")
    def test_local_hit_issues_only_head(self, mock_manifest_objects, mock_get_domain):
        digest = "sha256:" + "a" * 64
        local_manifest = MagicMock()
        mock_manifest_objects.filter.return_value.first.return_value = local_manifest

        head_downloader = MagicMock()
        head_downloader.fetch.return_value = _mock_response(digest)
        self._set_downloaders(head_downloader)

        manifest, response = self.view.fetch_manifest(self.remote, "latest")

        self.assertIs(manifest, local_manifest)
        self.remote.get_downloader.assert_called_once()
        head_downloader.fetch.assert_called_once()
        _, kwargs = head_downloader.fetch.call_args
        self.assertEqual(kwargs["extra_data"]["http_method"], "head")

    @patch("pulp_container.app.registry_api.get_domain")
    @patch("pulp_container.app.registry_api.models.Manifest.objects")
    def test_local_miss_falls_back_to_get(self, mock_manifest_objects, mock_get_domain):
        digest = "sha256:" + "b" * 64
        mock_manifest_objects.filter.return_value.first.return_value = None

        head_downloader = MagicMock()
        head_downloader.fetch.return_value = _mock_response(digest)
        get_downloader = MagicMock()
        get_downloader.fetch.return_value = _mock_response(digest)
        self._set_downloaders(head_downloader, get_downloader)

        manifest, response = self.view.fetch_manifest(self.remote, "latest")

        self.assertIsNone(manifest)
        self.assertIs(response, get_downloader.fetch.return_value)
        self.assertEqual(self.remote.get_downloader.call_count, 2)
        head_downloader.fetch.assert_called_once()
        get_downloader.fetch.assert_called_once()
        _, kwargs = get_downloader.fetch.call_args
        self.assertEqual(kwargs["extra_data"]["http_method"], "get")

    @patch("pulp_container.app.registry_api.get_domain")
    @patch("pulp_container.app.registry_api.models.Manifest.objects")
    def test_missing_digest_header_falls_back_to_get(self, mock_manifest_objects, mock_get_domain):
        mock_manifest_objects.filter.return_value.first.return_value = None

        head_downloader = MagicMock()
        head_downloader.fetch.return_value = _mock_response(digest=None)
        get_downloader = MagicMock()
        get_downloader.fetch.return_value = _mock_response("sha256:" + "c" * 64)
        self._set_downloaders(head_downloader, get_downloader)

        self.view.fetch_manifest(self.remote, "latest")

        self.assertEqual(self.remote.get_downloader.call_count, 2)
        get_downloader.fetch.assert_called_once()

    def test_404_on_head_raises_manifest_not_found(self):
        head_downloader = MagicMock()
        head_downloader.fetch.side_effect = ClientResponseError(
            request_info=MagicMock(), history=(), status=404
        )
        self._set_downloaders(head_downloader)

        with self.assertRaises(ManifestNotFound):
            self.view.fetch_manifest(self.remote, "missing-tag")

    def test_429_on_head_raises_throttled(self):
        head_downloader = MagicMock()
        head_downloader.fetch.side_effect = ClientResponseError(
            request_info=MagicMock(), history=(), status=429
        )
        self._set_downloaders(head_downloader)

        with self.assertRaises(Throttled):
            self.view.fetch_manifest(self.remote, "latest")

    def test_other_status_on_head_raises_bad_gateway(self):
        head_downloader = MagicMock()
        head_downloader.fetch.side_effect = ClientResponseError(
            request_info=MagicMock(), history=(), status=500, message="boom"
        )
        self._set_downloaders(head_downloader)

        with self.assertRaises(BadGateway):
            self.view.fetch_manifest(self.remote, "latest")

    def test_connection_error_on_head_raises_gateway_timeout(self):
        head_downloader = MagicMock()
        head_downloader.fetch.side_effect = ClientConnectionError()
        self._set_downloaders(head_downloader)

        with self.assertRaises(GatewayTimeout):
            self.view.fetch_manifest(self.remote, "latest")

    def test_timeout_on_head_raises_gateway_timeout(self):
        head_downloader = MagicMock()
        head_downloader.fetch.side_effect = TimeoutException()
        self._set_downloaders(head_downloader)

        with self.assertRaises(GatewayTimeout):
            self.view.fetch_manifest(self.remote, "latest")


if __name__ == "__main__":
    unittest.main()

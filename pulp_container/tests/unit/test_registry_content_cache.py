import json
from unittest.mock import AsyncMock, patch

from aiohttp.web import HTTPNotModified
from django.test import SimpleTestCase
from multidict import CIMultiDict

from pulp_container.app.cache import RegistryContentCache


class TestRegistryContentCache(SimpleTestCase):
    async def test_cached_response_removes_charset(self):
        cache = RegistryContentCache()
        entry = json.dumps(
            {
                "type": "Response",
                "expires": None,
                "headers": {"Content-Type": "application/json; charset=utf-8"},
                "body": b"{}".hex(),
            }
        )
        with patch.object(cache, "get", AsyncMock(return_value=entry)):
            response = await cache.make_response("key", "base-key")
        self.assertEqual(response.headers["Content-Type"], "application/json")
        self.assertEqual(response.body, b"{}")

    async def test_conditional_request_returns_not_modified(self):
        cache = RegistryContentCache()
        request = AsyncMock()
        request.headers = CIMultiDict({"If-None-Match": '"digest"'})
        entry = json.dumps(
            {
                "type": "Response",
                "expires": None,
                "headers": {"ETag": '"digest"'},
                "body": b"{}".hex(),
            }
        )
        with patch.object(cache, "get", AsyncMock(return_value=entry)):
            response = await cache.make_response("key", "base-key", request)
        self.assertIsInstance(response, HTTPNotModified)
        self.assertEqual(response.headers["ETag"], '"digest"')

    async def test_cache_miss(self):
        cache = RegistryContentCache()
        with patch.object(cache, "get", AsyncMock(return_value=None)):
            self.assertIsNone(await cache.make_response("key", "base-key", AsyncMock()))

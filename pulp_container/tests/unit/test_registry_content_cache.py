import inspect
import json
from unittest import skipUnless
from unittest.mock import AsyncMock, patch

from aiohttp.web import HTTPNotModified
from django.test import SimpleTestCase
from multidict import CIMultiDict

from pulpcore.plugin.cache import AsyncContentCache

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

    @skipUnless(
        "request" in inspect.signature(AsyncContentCache.make_response).parameters,
        "This pulpcore version does not support conditional cache requests",
    )
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
            self.assertIsNone(await cache.make_response("key", "base-key"))

    async def test_legacy_call_does_not_add_request_argument(self):
        cache = RegistryContentCache()

        async def legacy_make_response(instance, key, base_key):
            return None

        with patch.object(AsyncContentCache, "make_response", legacy_make_response):
            self.assertIsNone(await cache.make_response("key", "base-key"))

    async def test_request_is_forwarded(self):
        cache = RegistryContentCache()
        request = object()
        with patch.object(AsyncContentCache, "make_response", AsyncMock()) as make_response:
            make_response.return_value = None
            await cache.make_response("key", "base-key", request)
            make_response.assert_awaited_once_with("key", "base-key", request)
            make_response.reset_mock()
            await cache.make_response("key", "base-key", request=request)
            make_response.assert_awaited_once_with("key", "base-key", request=request)

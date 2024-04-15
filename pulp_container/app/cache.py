import json
import time

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import F, Value
from django.http import HttpResponseRedirect, HttpResponse, FileResponse as ApiFileResponse

from pulpcore.plugin.cache import CacheKeys, AsyncContentCache, SyncContentCache

from pulp_container.app.models import ContainerDistribution, ContainerPullThroughDistribution
from pulp_container.app.exceptions import RepositoryNotFound

ACCEPT_HEADER_KEY = "accept_header"
QUERY_KEY = "query"


class RegistryCache:
    """A class that overrides the default key specs."""

    def __init__(self, base_key=None, expires_ttl=None, auth=None):
        """Initialize the parent class with the plugin's specific keys."""
        updated_keys = (CacheKeys.path, CacheKeys.method, ACCEPT_HEADER_KEY)
        super().__init__(base_key=base_key, expires_ttl=expires_ttl, keys=updated_keys, auth=auth)


class RegistryContentCache(RegistryCache, AsyncContentCache):
    """A wrapper around the Redis content cache handler tailored for the content application."""

    ADD_TRAILING_SLASH = False

    def make_key(self, request):
        """Make a key composed of the request's path, method, host, and accept header."""
        accept_header = ",".join(sorted(request.headers.getall("accept", [])))
        all_keys = {
            CacheKeys.path: request.path,
            CacheKeys.method: request.method,
            CacheKeys.host: request.url.host,
            ACCEPT_HEADER_KEY: accept_header,
        }
        key = ":".join(all_keys[k] for k in self.keys)
        return key


class RegistryApiCache(RegistryCache, SyncContentCache):
    """A wrapper around the Redis content cache handler tailored for the registry API."""

    def make_key(self, request):
        """Make a key composed of the request's path, method, host, and accept header."""
        all_keys = {
            CacheKeys.path: request.path,
            CacheKeys.method: request.method,
            CacheKeys.host: request.get_host(),
            ACCEPT_HEADER_KEY: request.headers.get("accept", ""),
        }
        key = ":".join(all_keys[k] for k in self.keys)
        return key

    # overriding to serve layer blobs (bytes)
    def make_response(self, key, base_key):
        """Tries to find the cached entry and turn it into a proper response"""
        entry = self.get(key, base_key)
        if not entry:
            return None
        entry = json.loads(entry)
        response_type = entry.pop("type", None)
        if binary := entry.pop("content", None):
            # raw binary data were translated to their hexadecimal representation and saved in
            # the cache as a regular string; now, it is necessary to translate the data back
            # to its original representation that will be returned in the HTTP response BODY:
            # https://docs.aiohttp.org/en/stable/web_reference.html#response
            entry["content"] = bytes.fromhex(binary)
            response_type = "Response"
        # None means "doesn't expire", unset means "already expired".
        expires = entry.pop("expires", -1)
        if (not response_type or response_type not in self.RESPONSE_TYPES) or (
            expires and expires < time.time()
        ):
            # Bad entry, delete from cache
            self.delete(key, base_key)
            return None

        response = self.RESPONSE_TYPES[response_type](**entry)
        response.headers["X-PULP-CACHE"] = "HIT"
        return response

    # overriding to handle layer blobs (bytes) not raising exception when trying to decode it
    def make_entry(self, key, base_key, handler, args, kwargs, expires=None):
        """Gets the response for the request and try to turn it into a cacheable entry"""
        response = handler(*args, **kwargs)
        entry = {"headers": dict(response.headers), "status": response.status_code}
        if expires is not None:
            # Redis TTL is not sufficient: https://github.com/pulp/pulpcore/issues/4845
            entry["expires"] = expires + time.time()
        else:
            # Settings allow you to set None to mean "does not expire". Persist.
            entry["expires"] = None
        response.headers["X-PULP-CACHE"] = "MISS"
        if isinstance(response, HttpResponseRedirect):
            entry["redirect_to"] = str(response.headers["Location"])
            entry["type"] = "Redirect"
        elif isinstance(response, ApiFileResponse):
            entry["path"] = str(response.filename)
            entry["type"] = "FileResponse"
        elif isinstance(response, HttpResponse):
            entry["type"] = "Response"
            if isinstance(response.data, bytes):
                entry["content"] = response.data.hex()
            else:
                entry["content"] = response.content.decode("utf-8")
        else:
            # We don't cache StreamResponses or errors
            return response

        self.set(key, json.dumps(entry), expires, base_key=base_key)
        return response


def find_base_path_cached(request, cached):
    """
    Returns the base-path to use for the base-key in the cache

    Args:
        request (:class:`aiohttp.web.request`): The request from the client.
        cached (:class:`CacheAiohttp`): The Pulp cache

    Returns:
        str: The base-path associated with this request

    """
    path = request.resolver_match.kwargs["path"]
    path_exists = cached.exists(base_key=path)
    if path_exists:
        return path
    else:
        try:
            distro = ContainerDistribution.objects.get(base_path=path)
        except ObjectDoesNotExist:
            distro = (
                ContainerPullThroughDistribution.objects.annotate(path=Value(path))
                .filter(path__startswith=F("base_path"))
                .order_by("-base_path")
                .first()
            )
            if not distro:
                raise RepositoryNotFound(name=path)

        return distro.base_path


class FlatpakIndexStaticCache(SyncContentCache):
    def __init__(self, expires_ttl=None, auth=None):
        updated_keys = (QUERY_KEY,)
        super().__init__(
            base_key="/index/static", expires_ttl=expires_ttl, keys=updated_keys, auth=auth
        )

    def make_key(self, request):
        """Make a key composed of the request's query."""
        all_keys = {
            QUERY_KEY: request.query_params.urlencode(),
        }
        key = ":".join(all_keys[k] for k in self.keys)
        return key

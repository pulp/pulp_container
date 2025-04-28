import json
import time

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import F, Value

from django.http import HttpResponseRedirect, HttpResponse, FileResponse as ApiFileResponse
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer

from pulpcore.plugin.cache import CacheKeys, AsyncContentCache, SyncContentCache
from pulpcore.plugin.util import get_domain, cache_key

from pulp_container.app.models import ContainerDistribution, ContainerPullThroughDistribution
from pulp_container.app.exceptions import RepositoryNotFound

ACCEPT_HEADER_KEY = "accept_header"
DEFAULT_EXPIRES_TTL = settings.CACHE_SETTINGS["EXPIRES_TTL"]
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

    def make_entry(self, key, base_key, handler, args, kwargs, expires=DEFAULT_EXPIRES_TTL):
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
        elif isinstance(response, Response):
            response.accepted_renderer = JSONRenderer()
            response.accepted_media_type = "application/json"
            response.content_type = response.headers["Content-Type"]
            response.renderer_context = {}
            # response.render()
            entry["content"] = response.content.decode("utf-8")
            entry["type"] = "Response"
        elif isinstance(response, HttpResponse):
            entry["content"] = response.content.decode("utf-8")
            entry["type"] = "Response"
        else:
            # We don't cache StreamResponses or errors
            return response

        # TODO look into smaller format, maybe some compression on the text
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
    base_key = cache_key(path)
    path_exists = cached.exists(base_key=base_key)
    if path_exists:
        return base_key
    else:
        domain = get_domain()
        try:
            distro = ContainerDistribution.objects.get(base_path=path, pulp_domain=domain)
        except ObjectDoesNotExist:
            distro = (
                ContainerPullThroughDistribution.objects.annotate(path=Value(path))
                .filter(path__startswith=F("base_path"), pulp_domain=domain)
                .order_by("-base_path")
                .first()
            )
            if not distro:
                raise RepositoryNotFound(name=path)

        return cache_key(distro.base_path)


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

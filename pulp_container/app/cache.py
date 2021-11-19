from django.core.exceptions import ObjectDoesNotExist

from pulpcore.plugin.cache import CacheKeys, AsyncContentCache, SyncContentCache

from pulp_container.app.models import ContainerDistribution
from pulp_container.app.exceptions import RepositoryNotFound

ACCEPT_HEADER_KEY = "accept_header"


class RegistryCache:
    """A class that overrides the default key specs."""

    def __init__(self, base_key=None, expires_ttl=None, auth=None):
        """Initialize the parent class with the plugin's specific keys."""
        updated_keys = (CacheKeys.path, CacheKeys.method, ACCEPT_HEADER_KEY)
        super().__init__(base_key=base_key, expires_ttl=expires_ttl, keys=updated_keys, auth=auth)


class RegistryContentCache(RegistryCache, AsyncContentCache):
    """A wrapper around the Redis content cache handler tailored for the content application."""

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
            distro = ContainerDistribution.objects.select_related(
                "repository", "repository_version"
            ).get(base_path=path)
        except ObjectDoesNotExist:
            raise RepositoryNotFound(name=path)
        return distro.base_path

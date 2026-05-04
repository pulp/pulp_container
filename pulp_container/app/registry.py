import logging
import os

from aiohttp import web
from asgiref.sync import sync_to_async
from django.core.exceptions import ObjectDoesNotExist
from multidict import MultiDict

from pulpcore.plugin.content import ArtifactResponse, Handler, PathNotResolved
from pulpcore.plugin.models import Content, ContentArtifact
from pulpcore.plugin.util import get_domain

from pulp_container.app.cache import RegistryContentCache
from pulp_container.app.models import ContainerDistribution
from pulp_container.constants import BLOB_CONTENT_TYPE, EMPTY_BLOB

log = logging.getLogger(__name__)


class Registry(Handler):
    """
    A set of handlers for the Container Registry v2 API.
    """

    distribution_model = ContainerDistribution

    @staticmethod
    def _base_paths(path):
        """
        Get a list of base paths used to match a distribution.

        Args:
            path (str): The path component of the URL.

        Returns:
            list: Of base paths.

        """
        return [path]

    @staticmethod
    async def _dispatch(artifact, headers):
        """
        Stream a file back to the client.

        Stream the bits.

        Args:
            artifact (:class:`pulpcore.app.models.Artifact`): Artifact to respond with
            headers (dict): A dictionary of response headers.

        Raises:
            :class:`aiohttp.web_exceptions.HTTPFound`: When we need to redirect to the file
            NotImplementedError: If file is stored in a file storage we can't handle

        Returns:
            The :class:`aiohttp.web.StreamedResponse` for the Artifact.

        """
        domain = get_domain()
        full_headers = MultiDict()

        full_headers["Content-Type"] = headers["Content-Type"]
        full_headers["Docker-Content-Digest"] = headers["Docker-Content-Digest"]
        full_headers["Docker-Distribution-API-Version"] = "registry/2.0"

        if domain.storage_class == "pulpcore.app.models.storage.FileSystem":
            file = artifact.file
            path = os.path.join(domain.get_storage().location, file.name)
            if not os.path.exists(path):
                raise Exception("Expected path '{}' is not found".format(path))
            return web.FileResponse(path, headers=full_headers)
        else:
            return ArtifactResponse(artifact=artifact, headers=headers)

    @RegistryContentCache(
        base_key=lambda req, cac: Registry.find_base_path_cached(req, cac),
        auth=lambda req, cac, bk: Registry.auth_cached(req, cac, bk),
    )
    async def get_by_digest(self, request):
        """
        Return a response to the "GET" action.
        """
        path = request.match_info["path"]
        digest = "sha256:{digest}".format(digest=request.match_info["digest"])
        distribution = await sync_to_async(self._match_distribution)(path, add_trailing_slash=False)
        await sync_to_async(self._permit)(request, distribution)
        repository_version = await sync_to_async(distribution.get_repository_version)()
        if not repository_version:
            raise PathNotResolved(path)
        if digest == EMPTY_BLOB:
            return await Registry._empty_blob()

        repository = await repository_version.repository.acast()
        pending_blobs = repository.pending_blobs.values_list("pk")
        content = repository_version.content | Content.objects.filter(pk__in=pending_blobs)
        try:
            ca = await ContentArtifact.objects.select_related("artifact", "content").aget(
                content__in=content, relative_path=digest
            )
            ca_content = await ca.content.acast()
            media_type = BLOB_CONTENT_TYPE
            headers = {
                "Content-Type": media_type,
                "Docker-Content-Digest": ca_content.digest,
            }
        except ObjectDoesNotExist:
            raise PathNotResolved(path)
        else:
            artifact = ca.artifact
            if artifact:
                return await Registry._dispatch(artifact, headers)
            else:
                return await self._stream_content_artifact(request, web.StreamResponse(), ca)

    @staticmethod
    async def _empty_blob():
        # fmt: off
        empty_tar = [
            31, 139, 8, 0, 0, 9, 110, 136, 0, 255, 98, 24, 5, 163, 96, 20, 140, 88, 0, 8, 0, 0, 255,
            255, 46, 175, 181, 239, 0, 4, 0, 0,
        ]
        # fmt: on
        body = bytes(empty_tar)
        response_headers = {
            "Docker-Content-Digest": EMPTY_BLOB,
            "Content-Type": BLOB_CONTENT_TYPE,
            "Docker-Distribution-API-Version": "registry/2.0",
        }
        return web.Response(body=body, headers=response_headers)

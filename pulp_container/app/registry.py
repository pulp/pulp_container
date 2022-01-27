import logging
import os
from gettext import gettext as _

from asgiref.sync import sync_to_async

from aiohttp import web
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from multidict import MultiDict

from pulpcore.plugin.content import Handler, PathNotResolved
from pulpcore.plugin.models import ContentArtifact
from pulp_container.app.models import ContainerDistribution, Tag
from pulp_container.app.schema_convert import Schema2toSchema1ConverterWrapper
from pulp_container.app.utils import get_accepted_media_types
from pulp_container.constants import EMPTY_BLOB, MEDIA_TYPE

log = logging.getLogger(__name__)

v2_headers = MultiDict()
v2_headers["Docker-Distribution-API-Version"] = "registry/2.0"


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
    async def _dispatch(file, headers):
        """
        Stream a file back to the client.

        Stream the bits.

        Args:
            file (:class:`django.db.models.fields.files.FieldFile`): File to respond with
            headers (dict): A dictionary of response headers.

        Raises:
            :class:`aiohttp.web_exceptions.HTTPFound`: When we need to redirect to the file
            NotImplementedError: If file is stored in a file storage we can't handle

        Returns:
            The :class:`aiohttp.web.FileResponse` for the file.

        """
        path = os.path.join(settings.MEDIA_ROOT, file.name)
        if not os.path.exists(path):
            raise Exception(_("Expected path '{}' is not found").format(path))

        full_headers = MultiDict()

        full_headers["Content-Type"] = headers["Content-Type"]
        full_headers["Docker-Content-Digest"] = headers["Docker-Content-Digest"]
        full_headers["Docker-Distribution-API-Version"] = "registry/2.0"
        file_response = web.FileResponse(path, headers=full_headers)
        return file_response

    async def get_tag(self, request):
        """
        Match the path and stream either Manifest or ManifestList.

        Args:
            request(:class:`~aiohttp.web.Request`): The request to prepare a response for.

        Raises:
            PathNotResolved: The path could not be matched to a published file.
            PermissionError: When not permitted.

        Returns:
            :class:`aiohttp.web.StreamResponse` or :class:`aiohttp.web.FileResponse`: The response
                streamed back to the client.

        """
        self._reset_db_connection()

        path = request.match_info["path"]
        tag_name = request.match_info["tag_name"]
        distribution = await sync_to_async(self._match_distribution)(path)
        await sync_to_async(self._permit)(request, distribution)
        repository_version = await sync_to_async(distribution.get_repository_version)()
        accepted_media_types = get_accepted_media_types(request.headers)

        try:
            tag = await sync_to_async(Tag.objects.select_related("tagged_manifest").get)(
                pk__in=await sync_to_async(repository_version.get_content)(), name=tag_name
            )
        except ObjectDoesNotExist:
            raise PathNotResolved(tag_name)

        # we do not convert OCI to docker
        oci_mediatypes = [MEDIA_TYPE.MANIFEST_OCI, MEDIA_TYPE.INDEX_OCI]
        if (
            tag.tagged_manifest.media_type in oci_mediatypes
            and tag.tagged_manifest.media_type not in accepted_media_types
        ):
            log.warn(
                _("OCI format found, but the client only accepts {accepted_media_types}.").format(
                    accepted_media_types=accepted_media_types
                )
            )
            raise PathNotResolved(tag_name)

        # return schema1 (even in case only oci is requested)
        if tag.tagged_manifest.media_type == MEDIA_TYPE.MANIFEST_V1:
            return_media_type = MEDIA_TYPE.MANIFEST_V1_SIGNED
            response_headers = {
                "Content-Type": return_media_type,
                "Docker-Content-Digest": tag.tagged_manifest.digest,
            }
            return await self.dispatch_tag(request, tag, response_headers)

        # return what was found in case media_type is accepted header (docker, oci)
        if tag.tagged_manifest.media_type in accepted_media_types:
            return_media_type = tag.tagged_manifest.media_type
            response_headers = {
                "Content-Type": return_media_type,
                "Docker-Content-Digest": tag.tagged_manifest.digest,
            }
            return await self.dispatch_tag(request, tag, response_headers)

        # convert if necessary
        return await Registry.dispatch_converted_schema(tag, accepted_media_types, path)

    async def dispatch_tag(self, request, tag, response_headers):
        """
        Finds an artifact associated with a Tag and sends it to the client, otherwise tries
        to stream it.

        Args:
            request(:class:`~aiohttp.web.Request`): The request to prepare a response for.
            tag: Tag
            response_headers (dict): dictionary that contains the 'Content-Type' header to send
                with the response

        Returns:
            :class:`aiohttp.web.StreamResponse` or :class:`aiohttp.web.FileResponse`: The response
                streamed back to the client.

        """
        try:
            artifact = await sync_to_async(tag.tagged_manifest._artifacts.get)()
        except ObjectDoesNotExist:
            ca = await sync_to_async(lambda x: x[0])(tag.tagged_manifest.contentartifact_set.all())
            return await self._stream_content_artifact(request, web.StreamResponse(), ca)
        else:
            return await Registry._dispatch(artifact.file, response_headers)

    @staticmethod
    async def dispatch_converted_schema(tag, accepted_media_types, path):
        """
        Convert a manifest from the format schema 2 to the format schema 1.

        The format is converted on-the-go and created resources are not stored for further uses.
        The conversion is made after each request which does not accept the format for schema 2.

        Args:
            tag: A tag object which contains reference to tagged manifests and config blobs.
            accepted_media_types: Accepted media types declared in the accept header.
            path: A path of a repository.

        Raises:
            PathNotResolved: There was not found a valid conversion for the specified tag.

        Returns:
            :class:`aiohttp.web.StreamResponse` or :class:`aiohttp.web.Response`: The response
                streamed back to the client.

        """
        schema1_converter = Schema2toSchema1ConverterWrapper(tag, accepted_media_types, path)
        try:
            result = await sync_to_async(schema1_converter.convert)()
        except RuntimeError:
            raise PathNotResolved(tag.name)

        response_headers = {
            "Docker-Content-Digest": result.digest,
            "Content-Type": result.content_type,
            "Docker-Distribution-API-Version": "registry/2.0",
        }
        return web.Response(text=result.text, headers=response_headers)

    async def get_by_digest(self, request):
        """
        Return a response to the "GET" action.
        """
        self._reset_db_connection()

        path = request.match_info["path"]
        digest = "sha256:{digest}".format(digest=request.match_info["digest"])
        distribution = await sync_to_async(self._match_distribution)(path)
        await sync_to_async(self._permit)(request, distribution)
        repository_version = await sync_to_async(distribution.get_repository_version)()
        if digest == EMPTY_BLOB:
            return await Registry._empty_blob()
        try:
            ca = await sync_to_async(
                ContentArtifact.objects.select_related("artifact", "content").get
            )(
                content__in=await sync_to_async(repository_version.get_content)(),
                relative_path=digest,
            )
            ca_content = await sync_to_async(ca.content.cast)()
            headers = {
                "Content-Type": ca_content.media_type,
                "Docker-Content-Digest": ca_content.digest,
            }
        except ObjectDoesNotExist:
            raise PathNotResolved(path)
        else:
            artifact = ca.artifact
            if artifact:
                return await Registry._dispatch(artifact.file, headers)
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
        body = bytearray(empty_tar)
        response_headers = {
            "Docker-Content-Digest": EMPTY_BLOB,
            "Content-Type": MEDIA_TYPE.REGULAR_BLOB,
            "Docker-Distribution-API-Version": "registry/2.0",
        }
        return web.Response(body=body, headers=response_headers)

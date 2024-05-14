import json
import logging
import os

from asgiref.sync import sync_to_async

from contextlib import suppress
from urllib.parse import urljoin

from aiohttp import web
from aiohttp.client_exceptions import ClientResponseError, ClientConnectionError
from aiohttp.web_exceptions import HTTPTooManyRequests
from django_guid import set_guid
from django_guid.utils import generate_guid
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from multidict import MultiDict

from pulpcore.plugin.content import Handler, PathNotResolved
from pulpcore.plugin.models import RemoteArtifact, Content, ContentArtifact
from pulpcore.plugin.content import ArtifactResponse
from pulpcore.plugin.tasking import dispatch
from pulpcore.plugin.exceptions import TimeoutException

from pulp_container.app.cache import RegistryContentCache
from pulp_container.app.models import ContainerDistribution, Tag, Blob, Manifest, BlobManifest
from pulp_container.app.tasks import download_image_data
from pulp_container.app.utils import (
    calculate_digest,
    get_accepted_media_types,
    determine_media_type,
    save_artifact,
)
from pulp_container.constants import BLOB_CONTENT_TYPE, EMPTY_BLOB, MEDIA_TYPE, V2_ACCEPT_HEADERS

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
        full_headers = MultiDict()

        full_headers["Content-Type"] = headers["Content-Type"]
        full_headers["Docker-Content-Digest"] = headers["Docker-Content-Digest"]
        full_headers["Docker-Distribution-API-Version"] = "registry/2.0"

        if settings.DEFAULT_FILE_STORAGE == "pulpcore.app.models.storage.FileSystem":
            file = artifact.file
            path = os.path.join(settings.MEDIA_ROOT, file.name)
            if not os.path.exists(path):
                raise Exception("Expected path '{}' is not found".format(path))
            return web.FileResponse(path, headers=full_headers)
        else:
            return ArtifactResponse(artifact=artifact, headers=headers)

    @RegistryContentCache(
        base_key=lambda req, cac: Registry.find_base_path_cached(req, cac),
        auth=lambda req, cac, bk: Registry.auth_cached(req, cac, bk),
    )
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

        path = request.match_info["path"]
        tag_name = request.match_info["tag_name"]
        distribution = await sync_to_async(self._match_distribution)(path, add_trailing_slash=False)
        await sync_to_async(self._permit)(request, distribution)
        repository_version = await sync_to_async(distribution.get_repository_version)()
        if not repository_version:
            raise PathNotResolved(tag_name)

        distribution = await distribution.acast()
        try:
            tag = await Tag.objects.select_related("tagged_manifest").aget(
                pk__in=await sync_to_async(repository_version.get_content)(), name=tag_name
            )
        except ObjectDoesNotExist:
            if distribution.remote_id and distribution.pull_through_distribution_id:
                pull_downloader = await PullThroughDownloader.create(
                    distribution, repository_version, path, tag_name
                )
                raw_text_manifest, digest, media_type = await pull_downloader.download_manifest(
                    run_pipeline=True
                )
                headers = {
                    "Content-Type": media_type,
                    "Docker-Content-Digest": digest,
                    "Docker-Distribution-API-Version": "registry/2.0",
                }
                return web.Response(text=raw_text_manifest, headers=headers)
            else:
                raise PathNotResolved(tag_name)

        # check if the content is pulled via the pull-through caching distribution;
        # if yes, update the respective manifest from the remote when its digest changed
        if distribution.remote_id and distribution.pull_through_distribution_id:
            remote = await distribution.remote.acast()
            relative_url = "/v2/{name}/manifests/{tag}".format(
                name=remote.namespaced_upstream_name, tag=tag_name
            )
            tag_url = urljoin(remote.url, relative_url)
            downloader = remote.get_downloader(url=tag_url)
            try:
                response = await downloader.run(
                    extra_data={"headers": V2_ACCEPT_HEADERS, "http_method": "head"}
                )
            except (ClientResponseError, ClientConnectionError, TimeoutException):
                # the manifest is not available on the remote anymore
                # but the old one is still stored in the database
                pass
            else:
                digest = response.headers.get("docker-content-digest")
                if tag.tagged_manifest.digest != digest:
                    pull_downloader = await PullThroughDownloader.create(
                        distribution, repository_version, path, tag_name
                    )
                    pull_downloader.downloader = downloader
                    raw_text_manifest, digest, media_type = await pull_downloader.download_manifest(
                        run_pipeline=True
                    )
                    headers = {
                        "Content-Type": media_type,
                        "Docker-Content-Digest": digest,
                        "Docker-Distribution-API-Version": "registry/2.0",
                    }
                    return web.Response(text=raw_text_manifest, headers=headers)

        accepted_media_types = get_accepted_media_types(request.headers)

        # we do not convert OCI to docker
        oci_mediatypes = [MEDIA_TYPE.MANIFEST_OCI, MEDIA_TYPE.INDEX_OCI]
        if (
            tag.tagged_manifest.media_type in oci_mediatypes
            and tag.tagged_manifest.media_type not in accepted_media_types
        ):
            log.warn(
                "OCI format found, but the client only accepts {accepted_media_types}.".format(
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
            # TODO: BACKWARD COMPATIBILITY - remove after fully migrating to artifactless manifest
            if not tag.tagged_manifest.data:
                return await self.dispatch_tag(request, tag, response_headers)
            # END OF BACKWARD COMPATIBILITY
            return web.Response(text=tag.tagged_manifest.data, headers=response_headers)

        # return what was found in case media_type is accepted header (docker, oci)
        if tag.tagged_manifest.media_type in accepted_media_types:
            return_media_type = tag.tagged_manifest.media_type
            response_headers = {
                "Content-Type": return_media_type,
                "Docker-Content-Digest": tag.tagged_manifest.digest,
            }
            # TODO: BACKWARD COMPATIBILITY - remove after fully migrating to artifactless manifest
            if not tag.tagged_manifest.data:
                return await self.dispatch_tag(request, tag, response_headers)
            # END OF BACKWARD COMPATIBILITY
            return web.Response(text=tag.tagged_manifest.data, headers=response_headers)

        # return 404 in case the client is requesting docker manifest v2 schema 1
        raise PathNotResolved(tag_name)

    # TODO: BACKWARD COMPATIBILITY - remove after fully migrating to artifactless manifest
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
            artifact = await tag.tagged_manifest._artifacts.aget()
        except ObjectDoesNotExist:
            ca = await sync_to_async(lambda x: x[0])(tag.tagged_manifest.contentartifact_set.all())
            return await self._stream_content_artifact(request, web.StreamResponse(), ca)
        else:
            return await Registry._dispatch(artifact, response_headers)
        # END OF BACKWARD COMPATIBILITY

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
        pending_manifests = repository.pending_manifests.values_list("pk")
        pending_content = pending_blobs.union(pending_manifests)
        content = repository_version.content | Content.objects.filter(pk__in=pending_content)
        # "/pulp/container/{path:.+}/{content:(blobs|manifests)}/sha256:{digest:.+}"
        content_type = request.match_info["content"]

        try:
            if content_type == "manifests":
                manifest = await Manifest.objects.prefetch_related("contentartifact_set").aget(
                    digest=digest
                )
                headers = {
                    "Content-Type": manifest.media_type,
                    "Docker-Content-Digest": manifest.digest,
                }
                # TODO: BACKWARD COMPATIBILITY - remove after migrating to artifactless manifest
                if not manifest.data:
                    if saved_artifact := await manifest._artifacts.afirst():
                        return await Registry._dispatch(saved_artifact, headers)
                    else:
                        ca = await sync_to_async(lambda x: x[0])(manifest.contentartifact_set.all())
                        return await self._stream_content_artifact(
                            request, web.StreamResponse(), ca
                        )
                # END OF BACKWARD COMPATIBILITY
                return web.Response(text=manifest.data, headers=headers)
            elif content_type == "blobs":
                ca = await ContentArtifact.objects.select_related("artifact", "content").aget(
                    content__in=content, relative_path=digest
                )
                ca_content = await sync_to_async(ca.content.cast)()
                media_type = BLOB_CONTENT_TYPE
                headers = {
                    "Content-Type": media_type,
                    "Docker-Content-Digest": ca_content.digest,
                }
        except ObjectDoesNotExist:
            distribution = await distribution.acast()
            if distribution.remote_id and distribution.pull_through_distribution_id:
                pull_downloader = await PullThroughDownloader.create(
                    distribution, repository_version, path, digest
                )

                if content_type == "manifests":
                    (
                        raw_text_manifest,
                        digest,
                        media_type,
                    ) = await pull_downloader.download_manifest()
                    headers = {
                        "Content-Type": media_type,
                        "Docker-Content-Digest": digest,
                        "Docker-Distribution-API-Version": "registry/2.0",
                    }
                    return web.Response(text=raw_text_manifest, headers=headers)
                elif content_type == "blobs":
                    # there might be a case where the client has all the manifest data in place
                    # and tries to download only missing blobs; because of that, only the reference
                    # to a remote blob is returned (i.e., RemoteArtifact)
                    blob = await pull_downloader.init_remote_blob()
                    ca = await blob.contentartifact_set.afirst()
                    return await self._stream_content_artifact(request, web.StreamResponse(), ca)
                else:
                    raise RuntimeError("Only blobs or manifests are supported by the parser.")
            else:
                raise PathNotResolved(path)
        else:
            # else branch can be reached only for blob
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


class PullThroughDownloader:
    def __init__(self, distribution, remote, repository, repository_version, path, identifier):
        self.distribution = distribution
        self.remote = remote
        self.repository = repository
        self.repository_version = repository_version
        self.path = path
        self.identifier = identifier
        self.downloader = None

    @classmethod
    async def create(cls, distribution, repository_version, path, identifier):
        remote = await distribution.remote.acast()
        repository = await repository_version.repository.acast()
        return cls(distribution, remote, repository, repository_version, path, identifier)

    async def init_remote_blob(self):
        return await self.save_blob(self.identifier, None)

    async def download_manifest(self, run_pipeline=False):
        response = await self.run_manifest_downloader()

        with open(response.path, mode="r") as f:
            raw_text_data = f.read()

        if run_pipeline:
            await self.run_pipeline(raw_text_data)

        try:
            manifest_data = json.loads(raw_text_data)
        except json.decoder.JSONDecodeError:
            raise PathNotResolved(self.identifier)
        media_type = determine_media_type(manifest_data, response)
        if media_type in (MEDIA_TYPE.MANIFEST_V1_SIGNED, MEDIA_TYPE.MANIFEST_V1):
            digest = calculate_digest(raw_text_data)
        else:
            digest = f"sha256:{response.artifact_attributes['sha256']}"

        if media_type not in (MEDIA_TYPE.MANIFEST_LIST, MEDIA_TYPE.INDEX_OCI):
            # add the manifest and blobs to the repository to be able to stream it
            # in the next round when a client approaches the registry
            await self.init_pending_content(digest, manifest_data, media_type, raw_text_data)

        return raw_text_data, digest, media_type

    async def run_manifest_downloader(self):
        if self.downloader is None:
            relative_url = "/v2/{name}/manifests/{identifier}".format(
                name=self.remote.namespaced_upstream_name, identifier=self.identifier
            )
            url = urljoin(self.remote.url, relative_url)
            self.downloader = self.remote.get_downloader(url=url)

        try:
            response = await self.downloader.run(extra_data={"headers": V2_ACCEPT_HEADERS})
        except ClientResponseError as response_error:
            if response_error.status == 429:
                # the client could request the manifest outside the docker hub pull limit;
                # it is necessary to pass this information back to the client
                raise HTTPTooManyRequests()
            else:
                # TODO: do not mask out relevant errors, like HTTP 502
                raise PathNotResolved(self.path)

        return response

    async def run_pipeline(self, raw_text_manifest_data):
        set_guid(generate_guid())
        await sync_to_async(dispatch)(
            download_image_data,
            exclusive_resources=[self.repository_version.repository],
            kwargs={
                "repository_pk": self.repository_version.repository.pk,
                "remote_pk": self.remote.pk,
                "raw_text_manifest_data": raw_text_manifest_data,
                "tag_name": self.identifier,
            },
        )

    async def init_pending_content(self, digest, manifest_data, media_type, raw_text_data):
        if config := manifest_data.get("config", None):
            config_digest = config["digest"]
            config_blob = await self.save_config_blob(config_digest)
            await sync_to_async(self.repository.pending_blobs.add)(config_blob)
        else:
            config_blob = None

        manifest = Manifest(
            digest=digest,
            schema_version=(
                2
                if manifest_data["mediaType"] in (MEDIA_TYPE.MANIFEST_V2, MEDIA_TYPE.MANIFEST_OCI)
                else 1
            ),
            media_type=media_type,
            config_blob=config_blob,
            data=raw_text_data,
        )

        # skip if media_type of schema1
        if media_type in (MEDIA_TYPE.MANIFEST_V2, MEDIA_TYPE.MANIFEST_OCI):
            await sync_to_async(manifest.init_metadata)(manifest_data=manifest_data)

        try:
            await manifest.asave()
        except IntegrityError:
            manifest = await Manifest.objects.aget(digest=manifest.digest)
            await sync_to_async(manifest.touch)()
        await sync_to_async(self.repository.pending_manifests.add)(manifest)

        for layer in manifest_data["layers"]:
            blob = await self.save_blob(layer["digest"], manifest)
            await sync_to_async(self.repository.pending_blobs.add)(blob)

    async def save_blob(self, digest, manifest):
        blob = Blob(digest=digest)
        try:
            await blob.asave()
        except IntegrityError:
            blob = await Blob.objects.aget(digest=digest)
            await sync_to_async(blob.touch)()

        bm_rel = BlobManifest(manifest=manifest, manifest_blob=blob)
        with suppress(IntegrityError):
            await bm_rel.asave()

        ca = ContentArtifact(
            content=blob,
            artifact=None,
            relative_path=digest,
        )
        with suppress(IntegrityError):
            await ca.asave()

        relative_url = "/v2/{name}/blobs/{digest}".format(
            name=self.remote.namespaced_upstream_name, digest=digest
        )
        blob_url = urljoin(self.remote.url, relative_url)
        ra = RemoteArtifact(
            url=blob_url,
            sha256=digest[len("sha256:") :],
            content_artifact=ca,
            remote=self.remote,
        )
        with suppress(IntegrityError):
            await ra.asave()

        return blob

    async def save_config_blob(self, config_digest):
        blob_relative_url = "/v2/{name}/blobs/{digest}".format(
            name=self.remote.namespaced_upstream_name, digest=config_digest
        )
        blob_url = urljoin(self.remote.url, blob_relative_url)
        downloader = self.remote.get_downloader(url=blob_url)
        response = await downloader.run()

        response.artifact_attributes["file"] = response.path
        saved_artifact = await save_artifact(response.artifact_attributes)

        config_blob = Blob(digest=config_digest)
        try:
            await config_blob.asave()
        except IntegrityError:
            config_blob = await Blob.objects.aget(digest=config_digest)
            await sync_to_async(config_blob.touch)()

        content_artifact = ContentArtifact(
            content=config_blob,
            artifact=saved_artifact,
            relative_path=config_digest,
        )
        with suppress(IntegrityError):
            await content_artifact.asave()

        return config_blob

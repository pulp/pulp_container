import aiohttp
import asyncio
import base64
import hashlib
import json
import logging

from urllib.parse import urljoin, urlparse, urlunparse

from asgiref.sync import sync_to_async
from pulpcore.plugin.models import Artifact, ProgressReport, Remote
from pulpcore.plugin.stages import DeclarativeArtifact, DeclarativeContent, Stage, ContentSaver

from pulp_container.constants import (
    MEDIA_TYPE,
    SIGNATURE_API_EXTENSION_VERSION,
    SIGNATURE_HEADER,
    SIGNATURE_SOURCE,
    SIGNATURE_TYPE,
    V2_ACCEPT_HEADERS,
)
from pulp_container.app.models import (
    Blob,
    BlobManifest,
    Manifest,
    ManifestListManifest,
    ManifestSignature,
    Tag,
)
from pulp_container.app.utils import (
    extract_data_from_signature,
    urlpath_sanitize,
    determine_media_type,
    validate_manifest,
    calculate_digest,
    filter_resources,
    get_content_data,
)

log = logging.getLogger(__name__)


class ContainerFirstStage(Stage):
    """
    The first stage of a pulp_container sync pipeline.

    In this stage all the content is discovered, including the nested one.

    """

    def __init__(self, remote, signed_only):
        """Initialize the stage."""
        super().__init__()
        self.remote = remote
        self.deferred_download = self.remote.policy != Remote.IMMEDIATE
        self.signed_only = signed_only

        self.tag_dcs = []
        self.manifest_list_dcs = []
        self.manifest_dcs = []
        self.signature_dcs = []

    async def _download_manifest_data(self, manifest_url):
        downloader = self.remote.get_downloader(url=manifest_url)
        response = await downloader.run(extra_data={"headers": V2_ACCEPT_HEADERS})
        with open(response.path, "rb") as content_file:
            raw_bytes_data = content_file.read()
        response.artifact_attributes["file"] = response.path

        raw_text_data = raw_bytes_data.decode("utf-8")
        content_data = json.loads(raw_bytes_data)

        return content_data, raw_text_data, response

    async def _check_for_existing_manifest(self, download_tag):
        response = await download_tag

        digest = response.headers.get("docker-content-digest")

        if (
            manifest := await Manifest.objects.prefetch_related("contentartifact_set")
            .filter(digest=digest)
            .afirst()
        ):
            if raw_text_data := manifest.data:
                content_data = json.loads(raw_text_data)

            # TODO: BACKWARD COMPATIBILITY - remove after fully migrating to artifactless manifest
            elif saved_artifact := await manifest._artifacts.afirst():
                content_data, raw_bytes_data = await sync_to_async(get_content_data)(saved_artifact)
                raw_text_data = raw_bytes_data.decode("utf-8")
            # if artifact is not available (due to reclaim space) we will download it again
            else:
                content_data, raw_text_data, response = await self._download_manifest_data(
                    response.url
                )
            # END OF BACKWARD COMPATIBILITY

        else:
            content_data, raw_text_data, response = await self._download_manifest_data(response.url)

        return content_data, raw_text_data, response

    async def run(self):
        """
        ContainerFirstStage.
        """

        to_download = []
        BATCH_SIZE = 500

        # it can be whether a separate sigstore location or registry with extended signatures API
        signature_source = await self.get_signature_source()

        async with ProgressReport(
            message="Downloading tag list", code="sync.downloading.tag_list", total=1
        ) as pb:
            repo_name = self.remote.namespaced_upstream_name
            tag_list_url = "/v2/{name}/tags/list".format(name=repo_name)
            tag_list = await self.get_paginated_tag_list(tag_list_url, repo_name)
            tag_list = filter_resources(
                tag_list, self.remote.include_tags, self.remote.exclude_tags
            )
            await pb.aincrement()

        for tag_name in tag_list:
            relative_url = "/v2/{name}/manifests/{tag}".format(
                name=self.remote.namespaced_upstream_name, tag=tag_name
            )
            tag_url = urljoin(self.remote.url, relative_url)
            downloader = self.remote.get_downloader(url=tag_url)
            to_download.append(
                downloader.run(extra_data={"headers": V2_ACCEPT_HEADERS, "http_method": "head"})
            )

        async with ProgressReport(
            message="Processing Tags",
            code="sync.processing.tag",
            total=len(tag_list),
        ) as pb_parsed_tags:
            to_download_artifact = [
                self._check_for_existing_manifest(download_tag)
                for download_tag in asyncio.as_completed(to_download)
            ]

            for artifact in asyncio.as_completed(to_download_artifact):
                content_data, raw_text_data, response = await artifact

                digest = calculate_digest(raw_text_data)

                # Look for cosign signatures
                # cosign signature has a tag convention 'sha256-1234.sig'
                if self.signed_only and not signature_source:
                    if (
                        not (tag_name.endswith(".sig") and tag_name.startswith("sha256-"))
                        and f"sha256-{digest}.sig" not in tag_list
                    ):
                        # skip this tag, there is no corresponding signature
                        log.info(
                            "The unsigned image {digest} can't be synced "
                            "due to a requirement to sync signed content "
                            "only.".format(digest=digest)
                        )
                        # Count the skipped tagks as parsed too.
                        await pb_parsed_tags.aincrement()
                        continue

                media_type = determine_media_type(content_data, response)
                validate_manifest(content_data, media_type, digest)

                tag_name = response.url.split("/")[-1]
                tag_dc = DeclarativeContent(Tag(name=tag_name))

                if media_type in (MEDIA_TYPE.MANIFEST_LIST, MEDIA_TYPE.INDEX_OCI):
                    list_dc = self.create_manifest_list(
                        content_data, raw_text_data, media_type, digest=digest
                    )
                    for listed_manifest_task in asyncio.as_completed(
                        [
                            self.create_listed_manifest(manifest_data)
                            for manifest_data in content_data.get("manifests")
                        ]
                    ):
                        listed_manifest = await listed_manifest_task
                        man_dc = listed_manifest["manifest_dc"]
                        if signature_source is not None:
                            man_sig_dcs = await self.create_signatures(man_dc, signature_source)
                            if self.signed_only and not man_sig_dcs:
                                log.info(
                                    "The unsigned image {img_digest} which is a part of the "
                                    "manifest list {ml_digest} (tagged as `{tag}`) can't be "
                                    "synced due to a requirement to sync signed content only. "
                                    "The whole manifest list is skipped.".format(
                                        img_digest=man_dc.content.digest,
                                        ml_digest=list_dc.content.digest,
                                        tag=tag_name,
                                    )
                                )
                                # do not pass down the pipeline a manifest list with unsigned
                                # manifests.
                                break
                            self.signature_dcs.extend(man_sig_dcs)
                        list_dc.extra_data["listed_manifests"].append(listed_manifest)

                    else:
                        # Manifest indices can be signed too. It is not mandatory.
                        # If signature is available mirror it.
                        if signature_source is not None:
                            list_sig_dcs = await self.create_signatures(list_dc, signature_source)
                            if list_sig_dcs:
                                self.signature_dcs.extend(list_sig_dcs)
                        # only pass the manifest list and tag down the pipeline if there were no
                        # issues with signatures (no `break` in the `for` loop)
                        tag_dc.extra_data["tagged_manifest_dc"] = list_dc
                        for listed_manifest in list_dc.extra_data["listed_manifests"]:
                            await self.handle_blobs(
                                listed_manifest["manifest_dc"], listed_manifest["content_data"]
                            )
                            self.manifest_dcs.append(listed_manifest["manifest_dc"])
                        self.manifest_list_dcs.append(list_dc)
                        self.tag_dcs.append(tag_dc)

                else:
                    # Simple tagged manifest
                    man_dc = self.create_manifest(
                        content_data, raw_text_data, media_type, digest=digest
                    )
                    if signature_source is not None:
                        man_sig_dcs = await self.create_signatures(man_dc, signature_source)
                        if self.signed_only and not man_sig_dcs:
                            # do not pass down the pipeline unsigned manifests
                            continue
                        self.signature_dcs.extend(man_sig_dcs)
                    tag_dc.extra_data["tagged_manifest_dc"] = man_dc
                    await self.handle_blobs(man_dc, content_data)
                    self.tag_dcs.append(tag_dc)
                    self.manifest_dcs.append(man_dc)

                # Count the skipped tasks as parsed too.
                await pb_parsed_tags.aincrement()

                # Flush the queues to prevent overly excessive memory usage.
                # This will cap the number of in flight high level objects to about BATCH_SIZE.
                if (
                    len(self.tag_dcs)
                    + len(self.signature_dcs)
                    + len(self.manifest_dcs)
                    + len(self.manifest_list_dcs)
                    >= BATCH_SIZE
                ):
                    await self.resolve_flush()

        await self.resolve_flush()

    async def get_signature_source(self):
        """
        Find out where signatures come from: sigstore, extension API or not available at all.
        """
        if self.remote.sigstore:
            return SIGNATURE_SOURCE.SIGSTORE

        registry_v2_url = urljoin(self.remote.url, "v2/")
        extension_check_downloader = self.remote.get_noauth_downloader(url=registry_v2_url)
        response_headers = {}
        try:
            result = await extension_check_downloader.run()
            response_headers = result.headers
        except aiohttp.client_exceptions.ClientResponseError as exc:
            # ignore all HTTP errors, focus on the headers
            response_headers = dict(exc.headers)
        if response_headers.get(SIGNATURE_HEADER) == "1":
            return SIGNATURE_SOURCE.API_EXTENSION

    async def resolve_flush(self):
        """Resolve pending contents dependencies and put in the pipeline."""
        # Order matters! Things depended on must be resolved first.
        for manifest_dc in self.manifest_dcs:
            config_blob_dc = manifest_dc.extra_data.get("config_blob_dc")
            if config_blob_dc:
                manifest_dc.content.config_blob = await config_blob_dc.resolution()
                await sync_to_async(manifest_dc.content.init_labels)()
                manifest_dc.content.init_image_nature()
            for blob_dc in manifest_dc.extra_data["blob_dcs"]:
                # Just await here. They will be associated in the post_save hook.
                await blob_dc.resolution()
            await self.put(manifest_dc)
        self.manifest_dcs.clear()

        for manifest_list_dc in self.manifest_list_dcs:
            for listed_manifest in manifest_list_dc.extra_data["listed_manifests"]:
                # Just await here. They will be associated in the post_save hook.
                await listed_manifest["manifest_dc"].resolution()
            await self.put(manifest_list_dc)
        self.manifest_list_dcs.clear()

        for tag_dc in self.tag_dcs:
            tagged_manifest_dc = tag_dc.extra_data["tagged_manifest_dc"]
            tag_dc.content.tagged_manifest = await tagged_manifest_dc.resolution()
            await self.put(tag_dc)
        self.tag_dcs.clear()

        for signature_dc in self.signature_dcs:
            signed_manifest_dc = signature_dc.extra_data["signed_manifest_dc"]
            signature_dc.content.signed_manifest = await signed_manifest_dc.resolution()
            await self.put(signature_dc)
        self.signature_dcs.clear()

    async def get_paginated_tag_list(self, rel_link, repo_name):
        """
        Handle registries that have pagination enabled.
        """
        tag_list = []
        while True:
            link = urljoin(self.remote.url, rel_link)
            list_downloader = self.remote.get_downloader(url=link)
            # FIXME this can be rolledback after https://github.com/pulp/pulp_container/issues/1288
            # tags/list endpoint does not like any unnecessary headers to be sent
            await list_downloader.run(extra_data={"repo_name": repo_name, "headers": {}})
            with open(list_downloader.path) as tags_raw:
                tags_dict = json.loads(tags_raw.read())
                tag_list.extend(tags_dict["tags"])
            link = list_downloader.response_headers.get("Link")
            if link is None:
                break
            # according RFC5988 URI-reference can be relative or absolute
            _, _, path, params, query, fragm = urlparse(link.split(";")[0].strip(">, <"))
            rel_link = urlunparse(("", "", path, params, query, fragm))
        return tag_list

    async def handle_blobs(self, manifest_dc, content_data):
        """
        Handle blobs.
        """
        manifest_dc.extra_data["blob_dcs"] = []
        for layer in content_data.get("layers") or content_data.get("fsLayers"):
            if not self._include_layer(layer):
                continue
            blob_dc = self.create_blob(layer)
            manifest_dc.extra_data["blob_dcs"].append(blob_dc)
            await self.put(blob_dc)
        layer = content_data.get("config", None)
        if layer:
            blob_dc = self.create_blob(layer, deferred_download=False)
            manifest_dc.extra_data["config_blob_dc"] = blob_dc
            await self.put(blob_dc)

    def create_manifest_list(self, manifest_list_data, raw_text_data, media_type, digest=None):
        """
        Create a ManifestList.

        Args:
            manifest_list_data (dict): Data about a ManifestList
            raw_text_data: (str): The raw JSON representation of the ManifestList
            media_type (str): The type of the ManifestList
            digest (str): The digest of the ManifestList

        """
        if digest is None:
            digest = calculate_digest(raw_text_data)

        manifest_list = Manifest(
            digest=digest,
            schema_version=manifest_list_data["schemaVersion"],
            media_type=media_type,
            annotations=manifest_list_data.get("annotations", {}),
            data=raw_text_data,
        )

        manifest_list_dc = DeclarativeContent(content=manifest_list)
        manifest_list_dc.extra_data["listed_manifests"] = []
        return manifest_list_dc

    def create_manifest(self, manifest_data, raw_text_data, media_type, digest=None):
        """
        Create an Image Manifest.

        Args:
            manifest_data (dict): Data about a single new ImageManifest
            raw_text_data: (str): The raw JSON representation of the ImageManifest
            media_type (str): The type of the ImageManifest
            digest(str): THe digest of the ImageManifest

        """
        if digest is None:
            digest = calculate_digest(raw_text_data)

        manifest = Manifest(
            digest=digest,
            schema_version=manifest_data["schemaVersion"],
            media_type=media_type,
            data=raw_text_data,
            annotations=manifest_data.get("annotations", {}),
        )

        manifest_dc = DeclarativeContent(content=manifest)
        return manifest_dc

    def _create_signature_declarative_content(
        self, signature_raw, man_dc, name=None, signature_b64=None
    ):
        signature_json = extract_data_from_signature(signature_raw, man_dc.content.digest)
        if signature_json is None:
            return

        sig_digest = hashlib.sha256(signature_raw).hexdigest()
        signature = ManifestSignature(
            name=name or f"{man_dc.content.digest}@{sig_digest[:32]}",
            digest=f"sha256:{sig_digest}",
            type=SIGNATURE_TYPE.ATOMIC_SHORT,
            key_id=signature_json["signing_key_id"],
            timestamp=signature_json["signature_timestamp"],
            creator=signature_json["optional"].get("creator"),
            data=signature_b64 or base64.b64encode(signature_raw).decode(),
        )
        sig_dc = DeclarativeContent(
            content=signature,
            extra_data={"signed_manifest_dc": man_dc},
        )
        return sig_dc

    async def _download_and_instantiate_manifest(self, manifest_url, digest):
        content_data, raw_text_data, response = await self._download_manifest_data(manifest_url)
        media_type = determine_media_type(content_data, response)
        validate_manifest(content_data, media_type, digest)

        manifest = Manifest(
            digest=digest,
            schema_version=(
                2
                if content_data["mediaType"] in (MEDIA_TYPE.MANIFEST_V2, MEDIA_TYPE.MANIFEST_OCI)
                else 1
            ),
            media_type=content_data["mediaType"],
            data=raw_text_data,
            annotations=content_data.get("annotations", {}),
        )
        return content_data, manifest

    async def create_listed_manifest(self, manifest_data):
        """
        Create an Image Manifest from manifest data in a ManifestList.

        Args:
            manifest_data (dict): Data about a single new ImageManifest.

        """
        digest = manifest_data["digest"]
        relative_url = "/v2/{name}/manifests/{digest}".format(
            name=self.remote.namespaced_upstream_name, digest=digest
        )
        manifest_url = urljoin(self.remote.url, relative_url)

        if (
            manifest := await Manifest.objects.prefetch_related("contentartifact_set")
            .filter(digest=digest)
            .afirst()
        ):
            if manifest.data:
                content_data = json.loads(manifest.data)
            # TODO: BACKWARD COMPATIBILITY - remove after fully migrating to artifactless manifest
            elif saved_artifact := await manifest._artifacts.afirst():
                content_data, _ = await sync_to_async(get_content_data)(saved_artifact)
            # if artifact is not available (due to reclaim space) we will download it again
            else:
                content_data, manifest = await self._download_and_instantiate_manifest(
                    manifest_url, digest
                )
            # END OF BACKWARD COMPATIBILITY
        else:
            content_data, manifest = await self._download_and_instantiate_manifest(
                manifest_url, digest
            )

        platform = {}
        p = manifest_data["platform"]
        platform["architecture"] = p["architecture"]
        platform["os"] = p["os"]
        platform["features"] = p.get("features", "")
        platform["variant"] = p.get("variant", "")
        platform["os.version"] = p.get("os.version", "")
        platform["os.features"] = p.get("os.features", "")
        man_dc = DeclarativeContent(content=manifest)
        return {"manifest_dc": man_dc, "platform": platform, "content_data": content_data}

    def create_blob(self, blob_data, deferred_download=True):
        """
        Create blob.

        Args:
            blob_data (dict): Data about a blob
            deferred_download (bool): boolean that indicates whether not to download a blob
                immediatly. Config blob is downloaded regardless of the remote's settings

        """
        digest = blob_data.get("digest") or blob_data.get("blobSum")
        blob_artifact = Artifact(sha256=digest[len("sha256:") :])
        blob = Blob(digest=digest)
        relative_url = "/v2/{name}/blobs/{digest}".format(
            name=self.remote.namespaced_upstream_name, digest=digest
        )
        blob_url = urljoin(self.remote.url, relative_url)
        da = DeclarativeArtifact(
            artifact=blob_artifact,
            url=blob_url,
            relative_path=digest,
            remote=self.remote,
            deferred_download=deferred_download and self.deferred_download,
        )
        blob_dc = DeclarativeContent(content=blob, d_artifacts=[da])

        return blob_dc

    async def create_signatures(self, man_dc, signature_source):
        """
        Create signature declarative contents.

        Signatures are currently supported only for image manifests and not manifest lists.

        For sigstore, signatures are downloaded from a specified url. The number of signatures is
        unknown upfront, need to download them in order by incrementing the index until hit 404.

        Args:
            man_dc: Declarative content instance of a related Manifest
            signature_source: Source where to get signatures from
        """
        signature_dcs = []
        if signature_source == SIGNATURE_SOURCE.SIGSTORE:
            man_digest_reformatted = man_dc.content.digest.replace(":", "=")
            sig_relative_baseurl = f"{self.remote.upstream_name}@{man_digest_reformatted}"

            signature_counter = 1
            while True:
                signature_url = urlpath_sanitize(
                    self.remote.sigstore, sig_relative_baseurl, f"signature-{signature_counter}"
                )
                signature_downloader = self.remote.get_noauth_downloader(url=signature_url)
                try:
                    signature_download_result = await signature_downloader.run()
                except FileNotFoundError:
                    # 404 is fine, it means there are no or no more signatures available
                    break
                except aiohttp.client_exceptions.ClientResponseError as exc:
                    log.info(
                        "{} is not accessible, can't sync an image signature. "
                        "Error: {} {}".format(signature_url, exc.status, exc.message)
                    )

                with open(signature_download_result.path, "rb") as f:
                    signature_raw = f.read()

                signature_counter += 1
                sig_dc = self._create_signature_declarative_content(signature_raw, man_dc)
                if sig_dc:
                    signature_dcs.append(sig_dc)

        elif signature_source == SIGNATURE_SOURCE.API_EXTENSION:
            signatures_url = urlpath_sanitize(
                self.remote.url,
                "extensions/v2",
                self.remote.upstream_name,
                "signatures",
                man_dc.content.digest,
            )
            signatures_downloader = self.remote.get_downloader(url=signatures_url)
            # FIXME this can be rolledback after https://github.com/pulp/pulp_container/issues/1288
            # signature extensions endpoint does not like any unnecessary headers to be sent
            await signatures_downloader.run(extra_data={"headers": {}})
            with open(signatures_downloader.path) as signatures_fd:
                api_extension_signatures = json.loads(signatures_fd.read())
            for signature in api_extension_signatures.get("signatures", []):
                if (
                    signature.get("schemaVersion") == SIGNATURE_API_EXTENSION_VERSION
                    and signature.get("type") == SIGNATURE_TYPE.ATOMIC_SHORT
                ):
                    signature_base64 = signature.get("content")
                    if signature_base64 is None:
                        continue
                    signature_raw = base64.b64decode(signature_base64)
                    sig_dc = self._create_signature_declarative_content(
                        signature_raw, man_dc, signature.get("name"), signature_base64
                    )
                    if sig_dc:
                        signature_dcs.append(sig_dc)

        return signature_dcs

    def _include_layer(self, layer):
        """
        Decide whether to include a layer.

        Args:
            layer (dict): Layer reference.

        Returns:
            bool: True when the layer should be included.

        """
        foreign_excluded = not self.remote.include_foreign_layers
        layer_type = layer.get("mediaType", MEDIA_TYPE.REGULAR_BLOB)
        is_foreign = layer_type in (
            MEDIA_TYPE.FOREIGN_BLOB,
            MEDIA_TYPE.FOREIGN_BLOB_OCI_TAR,
            MEDIA_TYPE.FOREIGN_BLOB_OCI_TAR_GZIP,
            MEDIA_TYPE.FOREIGN_BLOB_OCI_TAR_ZSTD,
        )
        if is_foreign and foreign_excluded:
            log.debug("Foreign Layer: %(d)s EXCLUDED", dict(d=layer))
            return False
        return True


class ContainerContentSaver(ContentSaver):
    """Container specific content saver stage to add content associations."""

    def _post_save(self, batch):
        blob_manifests = []
        manifest_list_manifests = []
        manifest_lists = []
        for dc in batch:
            if "blob_dcs" in dc.extra_data:
                blob_manifests.extend(
                    (
                        BlobManifest(manifest=dc.content, manifest_blob=blob_dc.content)
                        for blob_dc in dc.extra_data["blob_dcs"]
                    )
                )
            if "listed_manifests" in dc.extra_data:
                manifest_lists.append(dc.content)
                for listed_manifest in dc.extra_data["listed_manifests"]:
                    manifest_dc = listed_manifest["manifest_dc"]
                    platform = listed_manifest["platform"]
                    manifest_list_manifests.append(
                        ManifestListManifest(
                            manifest_list=manifest_dc.content,
                            image_manifest=dc.content,
                            architecture=platform["architecture"],
                            os=platform["os"],
                            features=platform.get("features"),
                            variant=platform.get("variant"),
                            os_version=platform.get("os.version"),
                            os_features=platform.get("os.features"),
                        )
                    )
        if blob_manifests:
            BlobManifest.objects.bulk_create(blob_manifests, ignore_conflicts=True)
        if manifest_list_manifests:
            ManifestListManifest.objects.bulk_create(manifest_list_manifests, ignore_conflicts=True)

        # after creating the relation between listed manifests and manifest lists,
        # it is possible to initialize the nature of the corresponding manifest lists
        for ml in manifest_lists:
            if ml.init_manifest_list_nature():
                ml.save(update_fields=["is_bootable", "is_flatpak"])

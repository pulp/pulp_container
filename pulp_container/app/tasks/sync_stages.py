import aiohttp
import asyncio
import base64
import fnmatch
import hashlib
import json
import logging

from urllib.parse import urljoin, urlparse, urlunparse

from asgiref.sync import sync_to_async
from django.db import IntegrityError
from pulpcore.plugin.models import Artifact, ProgressReport, Remote
from pulpcore.plugin.stages import DeclarativeArtifact, DeclarativeContent, Stage, ContentSaver

from pulp_container.constants import (
    V2_ACCEPT_HEADERS,
    MEDIA_TYPE,
    SIGNATURE_API_EXTENSION_VERSION,
    SIGNATURE_HEADER,
    SIGNATURE_SOURCE,
    SIGNATURE_TYPE,
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
)

log = logging.getLogger(__name__)


def _save_artifact_blocking(artifact_attributes):
    saved_artifact = Artifact(**artifact_attributes)
    try:
        saved_artifact.save()
    except IntegrityError:
        del artifact_attributes["file"]
        saved_artifact = Artifact.objects.get(**artifact_attributes)
        saved_artifact.touch()
    return saved_artifact


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

    async def run(self):
        """
        ContainerFirstStage.
        """

        to_download = []
        BATCH_SIZE = 500

        signature_source = await self.get_signature_source()

        if signature_source is None and self.signed_only:
            raise ValueError(
                "It is requested to sync only signed content but no sigstore URL is "
                "provided. Please configure a `sigstore` on your Remote or set "
                "`signed_only` to `False` for your sync request."
            )

        async with ProgressReport(
            message="Downloading tag list", code="sync.downloading.tag_list", total=1
        ) as pb:
            repo_name = self.remote.namespaced_upstream_name
            tag_list_url = "/v2/{name}/tags/list".format(name=repo_name)
            tag_list = await self.get_paginated_tag_list(tag_list_url, repo_name)
            tag_list = self.filter_tags(tag_list)
            await pb.aincrement()

        for tag_name in tag_list:
            relative_url = "/v2/{name}/manifests/{tag}".format(
                name=self.remote.namespaced_upstream_name, tag=tag_name
            )
            url = urljoin(self.remote.url, relative_url)
            downloader = self.remote.get_downloader(url=url)
            to_download.append(downloader.run(extra_data={"headers": V2_ACCEPT_HEADERS}))

        async with ProgressReport(
            message="Processing Tags",
            code="sync.processing.tag",
            total=len(tag_list),
        ) as pb_parsed_tags:
            for download_tag in asyncio.as_completed(to_download):
                dl_res = await download_tag
                with open(dl_res.path, "rb") as content_file:
                    raw_data = content_file.read()
                dl_res.artifact_attributes["file"] = dl_res.path
                saved_artifact = await sync_to_async(_save_artifact_blocking)(
                    dl_res.artifact_attributes
                )

                tag_name = dl_res.url.split("/")[-1]
                tag_dc = DeclarativeContent(Tag(name=tag_name))

                content_data = json.loads(raw_data)
                media_type = determine_media_type(content_data, dl_res)
                digest = dl_res.artifact_attributes["sha256"]
                validate_manifest(content_data, media_type, digest)

                if media_type in (MEDIA_TYPE.MANIFEST_LIST, MEDIA_TYPE.INDEX_OCI):
                    list_dc = self.create_tagged_manifest_list(
                        tag_name, saved_artifact, content_data, media_type
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
                    man_dc = self.create_tagged_manifest(
                        tag_name, saved_artifact, content_data, raw_data, media_type
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

    def filter_tags(self, tag_list):
        """
        Filter tags by a list of included and excluded tags.
        """
        include_tags = self.remote.include_tags
        if include_tags:
            tag_list = [
                tag
                for tag in tag_list
                if any(fnmatch.fnmatch(tag, pattern) for pattern in include_tags)
            ]

        exclude_tags = self.remote.exclude_tags
        if exclude_tags:
            tag_list = [
                tag
                for tag in tag_list
                if not any(fnmatch.fnmatch(tag, pattern) for pattern in exclude_tags)
            ]

        return tag_list

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

    def create_tagged_manifest_list(self, tag_name, saved_artifact, manifest_list_data, media_type):
        """
        Create a ManifestList.

        Args:
            tag_name (str): A name of a tag
            saved_artifact (pulpcore.plugin.models.Artifact): A saved manifest's Artifact
            manifest_list_data (dict): Data about a ManifestList
            media_type (str): The type of a manifest

        """
        digest = f"sha256:{saved_artifact.sha256}"
        manifest_list = Manifest(
            digest=digest, schema_version=manifest_list_data["schemaVersion"], media_type=media_type
        )

        manifest_list_dc = self._create_manifest_declarative_content(
            manifest_list, saved_artifact, tag_name, digest
        )
        manifest_list_dc.extra_data["listed_manifests"] = []
        return manifest_list_dc

    def create_tagged_manifest(self, tag_name, saved_artifact, manifest_data, raw_data, media_type):
        """
        Create an Image Manifest.

        Args:
            tag_name (str): A name of a tag
            saved_artifact (pulpcore.plugin.models.Artifact): A saved manifest's Artifact
            manifest_data (dict): Data about a single new ImageManifest.
            raw_data: (str): The raw JSON representation of the ImageManifest.
            media_type (str): The type of a manifest

        """
        if media_type in (MEDIA_TYPE.MANIFEST_V2, MEDIA_TYPE.MANIFEST_OCI):
            digest = f"sha256:{saved_artifact.sha256}"
        else:
            digest = self._calculate_digest(raw_data)

        manifest = Manifest(
            digest=digest, schema_version=manifest_data["schemaVersion"], media_type=media_type
        )

        return self._create_manifest_declarative_content(manifest, saved_artifact, tag_name, digest)

    def _create_manifest_declarative_content(self, manifest, saved_artifact, tag_name, digest):
        relative_url = f"/v2/{self.remote.namespaced_upstream_name}/manifests/"
        da_digest = self._create_manifest_declarative_artifact(
            relative_url + digest, saved_artifact, digest
        )
        da_tag = self._create_manifest_declarative_artifact(
            relative_url + tag_name, saved_artifact, digest
        )

        man_dc = DeclarativeContent(content=manifest, d_artifacts=[da_digest, da_tag])
        return man_dc

    def _create_manifest_declarative_artifact(self, relative_url, saved_artifact, digest):
        url = urljoin(self.remote.url, relative_url)
        da = DeclarativeArtifact(
            artifact=saved_artifact,
            url=url,
            relative_path=digest,
            remote=self.remote,
            extra_data={"headers": V2_ACCEPT_HEADERS},
        )
        return da

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
        manifest = await sync_to_async(
            Manifest.objects.prefetch_related("contentartifact_set")
            .filter(digest=digest, _artifacts__isnull=False)
            .first
        )()
        if manifest:

            def _get_content_data_blocking():
                saved_artifact = manifest.contentartifact_set.first().artifact
                content_data = json.load(saved_artifact.file)
                saved_artifact.file.close()
                return saved_artifact, content_data

            saved_artifact, content_data = await sync_to_async(_get_content_data_blocking)()
        else:
            downloader = self.remote.get_downloader(url=manifest_url)
            dl_res = await downloader.run(extra_data={"headers": V2_ACCEPT_HEADERS})
            with open(dl_res.path, "rb") as content_file:
                raw_data = content_file.read()
            dl_res.artifact_attributes["file"] = dl_res.path
            saved_artifact = await sync_to_async(_save_artifact_blocking)(
                dl_res.artifact_attributes
            )
            content_data = json.loads(raw_data)
            media_type = determine_media_type(content_data, dl_res)
            validate_manifest(content_data, media_type, digest)

            manifest = Manifest(
                digest=digest,
                schema_version=2
                if manifest_data["mediaType"] in (MEDIA_TYPE.MANIFEST_V2, MEDIA_TYPE.MANIFEST_OCI)
                else 1,
                media_type=manifest_data["mediaType"],
            )
        da = DeclarativeArtifact(
            artifact=saved_artifact,
            url=manifest_url,
            relative_path=digest,
            remote=self.remote,
            extra_data={"headers": V2_ACCEPT_HEADERS},
        )
        platform = {}
        p = manifest_data["platform"]
        platform["architecture"] = p["architecture"]
        platform["os"] = p["os"]
        platform["features"] = p.get("features", "")
        platform["variant"] = p.get("variant", "")
        platform["os.version"] = p.get("os.version", "")
        platform["os.features"] = p.get("os.features", "")
        man_dc = DeclarativeContent(
            content=manifest,
            d_artifacts=[da],
        )
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

    def _calculate_digest(self, manifest):
        """
        Calculate the requested digest of the ImageManifest, given in JSON.

        Args:
            manifest (str):  The raw JSON representation of the Manifest.

        Returns:
            str: The digest of the given ImageManifest

        """
        decoded_manifest = json.loads(manifest)
        if "signatures" in decoded_manifest:
            # This manifest contains signatures. Unfortunately, the Docker manifest digest
            # is calculated on the unsigned version of the Manifest so we need to remove the
            # signatures. To do this, we will look at the 'protected' key within the first
            # signature. This key indexes a (malformed) base64 encoded JSON dictionary that
            # tells us how many bytes of the manifest we need to keep before the signature
            # appears in the original JSON and what the original ending to the manifest was after
            # the signature block. We will strip out the bytes after this cutoff point, add back the
            # original ending, and then calculate the sha256 sum of the transformed JSON to get the
            # digest.
            protected = decoded_manifest["signatures"][0]["protected"]
            # Add back the missing padding to the protected block so that it is valid base64.
            protected = self._pad_unpadded_b64(protected)
            # Now let's decode the base64 and load it as a dictionary so we can get the length
            protected = base64.b64decode(protected)
            protected = json.loads(protected)
            # This is the length of the signed portion of the Manifest, except for a trailing
            # newline and closing curly brace.
            signed_length = protected["formatLength"]
            # The formatTail key indexes a base64 encoded string that represents the end of the
            # original Manifest before signatures. We will need to add this string back to the
            # trimmed Manifest to get the correct digest. We'll do this as a one liner since it is
            # a very similar process to what we've just done above to get the protected block
            # decoded.
            signed_tail = base64.b64decode(self._pad_unpadded_b64(protected["formatTail"]))
            # Now we can reconstruct the original Manifest that the digest should be based on.
            manifest = manifest[:signed_length] + signed_tail

        return "sha256:{digest}".format(digest=hashlib.sha256(manifest).hexdigest())

    def _pad_unpadded_b64(self, unpadded_b64):
        """
        Fix bad padding.

        Docker has not included the required padding at the end of the base64 encoded
        'protected' block, or in some encased base64 within it. This function adds the correct
        number of ='s signs to the unpadded base64 text so that it can be decoded with Python's
        base64 library.

        Args:
            unpadded_b64 (str): The unpadded base64 text.

        Returns:
            str: The same base64 text with the appropriate number of ='s symbols.

        """
        # The Pulp team has not observed any newlines or spaces within the base64 from Docker, but
        # Docker's own code does this same operation so it seemed prudent to include it here.
        # See lines 167 to 168 here:
        # https://github.com/docker/libtrust/blob/9cbd2a1374f46905c68a4eb3694a130610adc62a/util.go
        unpadded_b64 = unpadded_b64.replace("\n", "").replace(" ", "")
        # It is illegal base64 for the remainder to be 1 when the length of the block is
        # divided by 4.
        if len(unpadded_b64) % 4 == 1:
            raise ValueError("Invalid base64: {t}".format(t=unpadded_b64))
        # Add back the missing padding characters, based on the length of the encoded string
        paddings = {0: "", 2: "==", 3: "="}
        return unpadded_b64 + paddings[len(unpadded_b64) % 4]


class ContainerContentSaver(ContentSaver):
    """Container specific content saver stage to add content associations."""

    def _post_save(self, batch):
        blob_manifests = []
        manifest_list_manifests = []
        for dc in batch:
            if "blob_dcs" in dc.extra_data:
                blob_manifests.extend(
                    (
                        BlobManifest(manifest=dc.content, manifest_blob=blob_dc.content)
                        for blob_dc in dc.extra_data["blob_dcs"]
                    )
                )
            if "listed_manifests" in dc.extra_data:
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

import asyncio
import base64
import hashlib

from aiofiles import tempfile
from asgiref.sync import sync_to_async
from django.conf import settings
from django.db.models import Q

from pulpcore.plugin.models import Repository

from pulp_container.app.models import (
    ManifestSignature,
    ManifestSigningService,
    Tag,
)

from pulp_container.app.utils import extract_data_from_signature
from pulp_container.constants import (
    MANIFEST_MEDIA_TYPES,
    SIGNATURE_TYPE,
)

semaphore = asyncio.Semaphore(settings.MAX_PARALLEL_SIGNING_TASKS)


def sign(repository_pk, signing_service_pk, reference, tags_list=None):
    """
    Create a new repository version by signing manifests.

    Create signature for each manifest that is specified and add it to the repo.
    If no manifests were specified, then sign all manifests in the repo.

    What manifests to sign is identified by tags.
    Manifest lists are signed too. Image manifests from the manifest lists are signed by tags.

    Args:
        repository_pk (uuid): A pk for a Repository for which a new Repository Version should be
                             created.
        signing_service_pk (uuid): A pk of the signing service to use.
        reference (str): Reference that will be used to produce signature.
        tags_list (list): List of PKs for :class:`~pulp_container.app.models.Tag` manifests of which
                          should be signed.

    """
    repository = Repository.objects.get(pk=repository_pk).cast()
    latest_version = repository.latest_version()
    if tags_list:
        latest_repo_content_tags = latest_version.content.filter(
            pulp_type=Tag.get_pulp_type(),
            pk__in=tags_list,
        )
    else:
        latest_repo_content_tags = latest_version.content.filter(pulp_type=Tag.get_pulp_type())
    latest_repo_tags = (
        Tag.objects.filter(pk__in=latest_repo_content_tags)
        .select_related("tagged_manifest")
        .exclude(Q(name__endswith=".sig") | Q(name__endswith=".att") | Q(name__endswith=".sbom"))
    )
    signing_service = ManifestSigningService.objects.get(pk=signing_service_pk)

    async def sign_manifests():
        added_signatures = []

        async for tag in latest_repo_tags.aiterator():
            tagged_manifest = tag.tagged_manifest
            docker_reference = ":".join((reference, tag.name))
            signature_pk = await create_signature(
                tagged_manifest, docker_reference, signing_service
            )
            added_signatures.append(signature_pk)
            if tagged_manifest.media_type in MANIFEST_MEDIA_TYPES.LIST:
                # parse ML and sign per-arches
                manifests_iterator = tagged_manifest.listed_manifests.aiterator()
                async for manifest in manifests_iterator:
                    signature_pk = await create_signature(
                        manifest, docker_reference, signing_service
                    )
                    added_signatures.append(signature_pk)

        return added_signatures

    added_signatures = asyncio.run(sign_manifests())
    added_signatures_qs = ManifestSignature.objects.filter(pk__in=added_signatures)
    with repository.new_version() as new_version:
        new_version.add_content(added_signatures_qs)


async def create_signature(manifest, reference, signing_service):
    """
    Create manifest signature.

    Created signature is extracted,parsed and a ManifestSignature is saved.

    Args:
        manifest (models.Manifest): Manifest which is intended to be signed.
        reference (str): reference that will be used in signature's docker-reference.
        signing_service (models.ManifestSigingService): signing service that will be used.

    Returns:
        pk of created ManifestSignature.

    """
    async with semaphore:
        # download and write file for object storage
        if not manifest.data:
            # TODO: BACKWARD COMPATIBILITY - remove after fully migrating to artifactless manifest
            artifact = await manifest._artifacts.aget()
            if settings.DEFAULT_FILE_STORAGE != "pulpcore.app.models.storage.FileSystem":
                async with tempfile.NamedTemporaryFile(dir=".", mode="wb", delete=False) as tf:
                    await tf.write(await sync_to_async(artifact.file.read)())
                    await tf.flush()
                artifact.file.close()
                manifest_path = tf.name
            else:
                manifest_path = artifact.file.path
            # END OF BACKWARD COMPATIBILITY
        else:
            async with tempfile.NamedTemporaryFile(dir=".", mode="wb", delete=False) as tf:
                await tf.write(manifest.data.encode("utf-8"))
                await tf.flush()
            manifest_path = tf.name

        async with tempfile.NamedTemporaryFile(dir=".", prefix="signature") as tf:
            sig_path = tf.name

        signed = await signing_service.asign(
            manifest_path, env_vars={"REFERENCE": reference, "SIG_PATH": sig_path}
        )

        with open(signed["signature_path"], "rb") as sig_fp:
            data = sig_fp.read()
            encoded_sig = base64.b64encode(data).decode()
            sig_digest = hashlib.sha256(data).hexdigest()
            sig_json = extract_data_from_signature(data, manifest.digest)
            manifest_digest = sig_json["critical"]["image"]["docker-manifest-digest"]

            signature = ManifestSignature(
                name=f"{manifest_digest}@{sig_digest[:32]}",
                digest=f"sha256:{sig_digest}",
                type=SIGNATURE_TYPE.ATOMIC_SHORT,
                key_id=sig_json["signing_key_id"],
                timestamp=sig_json["signature_timestamp"],
                creator=sig_json["optional"].get("creator"),
                data=encoded_sig,
                signed_manifest=manifest,
            )
            await signature.asave()

    return signature.pk

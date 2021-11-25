import base64
import hashlib
import os
import tempfile

from django.conf import settings

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


def sign(repository_pk, signing_service_pk, reference, tags_list=None):
    """
    Create a new repository version by signing manifests.

    Create signature for each manifest that is specified and add it to the repo.
    If no manifests were specified, then sign all manifests in the repo.

    What manifests to sign is identified by tag.
    Manifest lists are not signed. Image manifests from manifest list are signed by digest.

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
            pulp_type=Tag.get_pulp_type(), pk__in=tags_list
        )
    else:
        latest_repo_content_tags = latest_version.content.filter(pulp_type=Tag.get_pulp_type())
    latest_repo_tags = Tag.objects.filter(pk__in=latest_repo_content_tags)
    signing_service = ManifestSigningService.objects.get(pk=signing_service_pk)
    added_signatures = []
    already_signed = []
    for tag in latest_repo_tags:
        tagged_manifest = tag.tagged_manifest
        if tagged_manifest.media_type in MANIFEST_MEDIA_TYPES.IMAGE:
            signature_pk = create_signature(
                tagged_manifest, ":".join((reference, tag.name)), signing_service
            )
            added_signatures.append(signature_pk)
        elif tagged_manifest.media_type in MANIFEST_MEDIA_TYPES.LIST:
            # parse ML and sign per-arches by digest
            for manifest in tagged_manifest.listed_manifests.iterator():
                # image manifests can be present in multiple ML within the repo
                if manifest.digest not in already_signed:
                    signature_pk = create_signature(
                        manifest, ":".join((reference, manifest.digest)), signing_service
                    )
                    already_signed.append(manifest.digest)
                    added_signatures.append(signature_pk)

    added_signatures_qs = ManifestSignature.objects.filter(pk__in=added_signatures)
    with repository.new_version() as new_version:
        new_version.add_content(added_signatures_qs)


def create_signature(manifest, reference, signing_service):
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
    with tempfile.TemporaryDirectory(".") as working_directory:
        # download and write file for object storage
        if settings.DEFAULT_FILE_STORAGE != "pulpcore.app.models.storage.FileSystem":
            manifest_file = tempfile.NamedTemporaryFile(dir=working_directory, delete=False)
            artifact = manifest._artifacts.get()
            manifest_file.write(artifact.file.read())
            manifest_file.flush()
            artifact.file.close()
            manifest_path = manifest_file.name
        else:
            manifest_path = manifest._artifacts.get().file.path
        sig_path = os.path.join(working_directory, "signature")

        signed = signing_service.sign(
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
            signature.save()

    return signature.pk

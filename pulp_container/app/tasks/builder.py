import json
import os
import shutil
import subprocess
import tempfile
from uuid import uuid4

from pulp_container.app.models import (
    Blob,
    BlobManifest,
    ContainerRepository,
    Manifest,
    Tag,
)
from pulp_container.constants import MEDIA_TYPE
from pulpcore.plugin.models import Artifact, ContentArtifact


def get_or_create_blob(layer_json, manifest, path):
    """
    Creates Blob from json snippet of manifest.json

    Args:
        layer_json (json): json
        manifest (class:`pulp_container.app.models.Manifest`): The manifest
        path (str): Path of the directory that contains layer

    Returns:
        class:`pulp_container.app.models.Blob`

    """
    try:
        blob = Blob.objects.get(digest=layer_json["digest"])
        blob.touch()
    except Blob.DoesNotExist:
        layer_file_name = "{}{}".format(path, layer_json["digest"][7:])
        layer_artifact = Artifact.init_and_validate(layer_file_name)
        layer_artifact.save()
        blob = Blob(digest=layer_json["digest"], media_type=layer_json["mediaType"])
        blob.save()
        ContentArtifact(
            artifact=layer_artifact, content=blob, relative_path=layer_json["digest"]
        ).save()
    if blob.media_type != MEDIA_TYPE.CONFIG_BLOB_OCI:
        BlobManifest(manifest=manifest, manifest_blob=blob).save()
    return blob


def add_image_from_directory_to_repository(path, repository, tag):
    """
    Creates a Manifest and all blobs from a directory with OCI image

    Args:
        path (str): Path to directory with the OCI image
        repository (class:`pulpcore.plugin.models.Repository`): The destination repository
        tag (str): Tag name for the new image in the repository

    Returns:
        A class:`pulpcore.plugin.models.RepositoryVersion` that contains the new OCI container
        image and tag.

    """
    manifest_path = "{}manifest.json".format(path)
    manifest_artifact = Artifact.init_and_validate(manifest_path)
    manifest_artifact.save()
    manifest_digest = "sha256:{}".format(manifest_artifact.sha256)
    manifest = Manifest(
        digest=manifest_digest, schema_version=2, media_type=MEDIA_TYPE.MANIFEST_OCI
    )
    manifest.save()
    ContentArtifact(
        artifact=manifest_artifact, content=manifest, relative_path=manifest_digest
    ).save()
    tag = Tag(name=tag, tagged_manifest=manifest)
    tag.save()
    with repository.new_version() as new_repo_version:
        new_repo_version.add_content(Manifest.objects.filter(pk=manifest.pk))
        new_repo_version.add_content(Tag.objects.filter(pk=tag.pk))
        with open(manifest_artifact.file.path, "r") as manifest_file:
            manifest_json = json.load(manifest_file)
            config_blob = get_or_create_blob(manifest_json["config"], manifest, path)
            manifest.config_blob = config_blob
            manifest.save()
            new_repo_version.add_content(Blob.objects.filter(pk=config_blob.pk))
            for layer in manifest_json["layers"]:
                blob = get_or_create_blob(layer, manifest, path)
                new_repo_version.add_content(Blob.objects.filter(pk=blob.pk))
    return new_repo_version


def build_image_from_containerfile(
    containerfile_pk=None, artifacts={}, repository_pk=None, tag=None
):
    """
    Builds an OCI container image from a Containerfile.

    The artifacts are made available inside the build container at the paths specified by their
    values. The Containerfile can make use of these files during build process.

    Args:
        containerfile_pk (str): The pk of an Artifact that contains the Containerfile
        artifacts (dict): A dictionary where each key is an artifact PK and the value is it's
                          relative path (name) inside the /pulp_working_directory of the build
                          container executing the Containerfile.
        repository_pk (str): The pk of a Repository to add the OCI container image
        tag (str): Tag name for the new image in the repository

    Returns:
        A class:`pulpcore.plugin.models.RepositoryVersion` that contains the new OCI container
        image and tag.

    """
    containerfile = Artifact.objects.get(pk=containerfile_pk)
    repository = ContainerRepository.objects.get(pk=repository_pk)
    name = str(uuid4())
    with tempfile.TemporaryDirectory(".") as working_directory:
        path = "{}/".format(working_directory.path)
        for key, val in artifacts.items():
            artifact = Artifact.objects.get(pk=key)
            dirs = os.path.split(val)[0]
            if dirs:
                os.makedirs(dirs)

            shutil.copy(artifact.file.path, "{}{}".format(path, val))
        bud_cp = subprocess.run(
            ["buildah", "bud", "-f", containerfile.file.path, "-t", name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if bud_cp.returncode != 0:
            raise Exception(bud_cp.stderr)
        image_dir = "{}image/".format(path)
        os.makedirs(image_dir)
        push_cp = subprocess.run(
            ["buildah", "push", "-f", "oci", name, "dir:{}".format(image_dir)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if push_cp.returncode != 0:
            raise Exception(push_cp.stderr)
        repository_version = add_image_from_directory_to_repository(image_dir, repository, tag)

    return repository_version

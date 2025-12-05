import json
import os
import shutil
import subprocess
import tempfile
from uuid import uuid4

from pulpcore.plugin.models import (
    Artifact,
    ContentArtifact,
    Content,
    PulpTemporaryFile,
)
from pulpcore.plugin.util import get_domain

from pulp_container.constants import MEDIA_TYPE
from pulp_container.app.models import (
    Blob,
    BlobManifest,
    ContainerRepository,
    Manifest,
    Tag,
)
from pulp_container.app.utils import calculate_digest


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
    domain = get_domain()
    try:
        blob = Blob.objects.get(digest=layer_json["digest"], _pulp_domain=domain)
        blob.touch()
    except Blob.DoesNotExist:
        layer_file_name = os.path.join(path, layer_json["digest"][7:])
        layer_artifact = Artifact.init_and_validate(layer_file_name)
        layer_artifact.save()
        blob = Blob(digest=layer_json["digest"])
        blob.save()
        ContentArtifact(
            artifact=layer_artifact, content=blob, relative_path=layer_json["digest"]
        ).save()
    if layer_json["mediaType"] != MEDIA_TYPE.CONFIG_BLOB_OCI:
        BlobManifest.objects.get_or_create(manifest=manifest, manifest_blob=blob)
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
    domain = get_domain()
    manifest_path = os.path.join(path, "manifest.json")

    with open(manifest_path, "rb") as f:
        bytes_data = f.read()
    manifest_digest = calculate_digest(bytes_data)
    manifest_text_data = bytes_data.decode("utf-8")

    manifest, _ = Manifest.objects.get_or_create(
        digest=manifest_digest,
        schema_version=2,
        media_type=MEDIA_TYPE.MANIFEST_OCI,
        data=manifest_text_data,
        _pulp_domain=domain,
    )
    tag, _ = Tag.objects.get_or_create(name=tag, tagged_manifest=manifest, _pulp_domain=domain)

    with repository.new_version() as new_repo_version:
        manifest_json = json.loads(manifest_text_data)
        manifest.init_metadata(manifest_json)

        config_blob = get_or_create_blob(manifest_json["config"], manifest, path)
        manifest.config_blob = config_blob
        manifest.init_architecture_and_os()

        pks_to_add = []
        compressed_size = 0
        for layer in manifest_json["layers"]:
            compressed_size += layer.get("size")
            pks_to_add.append(get_or_create_blob(layer, manifest, path).pk)
        manifest.compressed_image_size = compressed_size
        manifest.save()

        pks_to_add.extend([manifest.pk, tag.pk, config_blob.pk])
        new_repo_version.add_content(Content.objects.filter(pk__in=pks_to_add))

    return new_repo_version


def build_image(
    containerfile_name=None,
    containerfile_tempfile_pk=None,
    build_context_pk=None,
    repository_pk=None,
    tag=None,
):
    """
    Builds an OCI container image from a Containerfile.

    The artifacts are made available inside the build container at the paths specified by their
    values. The Containerfile can make use of these files during build process.

    Args:
        containerfile_name (str): The Containerfile relative_path from the build_context repository
        containerfile_tempfile_pk (str): The pk of a PulpTemporaryFile that contains
                                         the Containerfile
        build_context_pk (str): The pk of the RepositoryVersion used as the build context
        repository_pk (str): The pk of a Repository to add the OCI container image
        tag (str): Tag name for the new image in the repository

    Returns:
        A class:`pulpcore.plugin.models.RepositoryVersion` that contains the new OCI container
        image and tag.

    """
    if not containerfile_tempfile_pk and not containerfile_name:
        raise RuntimeError("Neither a name nor temporary file for the Containerfile was specified.")

    if containerfile_tempfile_pk:
        containerfile_artifact = PulpTemporaryFile.objects.get(pk=containerfile_tempfile_pk)

    repository = ContainerRepository.objects.get(pk=repository_pk)
    name = str(uuid4())
    with tempfile.TemporaryDirectory(dir=".") as working_directory:
        working_directory = os.path.abspath(working_directory)
        context_path = os.path.join(working_directory, "context")
        os.makedirs(context_path, exist_ok=True)

        if build_context_pk:
            content_artifacts = ContentArtifact.objects.filter(
                content__pulp_type="file.file", content__repositories__in=[build_context_pk]
            ).order_by("-content__pulp_created")
            for content_artifact in content_artifacts.select_related("artifact").iterator():
                if content_artifact.relative_path == containerfile_name:
                    containerfile_artifact = content_artifact.artifact
                    continue
                _copy_file_from_artifact(
                    context_path, content_artifact.relative_path, content_artifact.artifact.file
                )

        containerfile_name = containerfile_name or "Containerfile"
        _copy_file_from_artifact(working_directory, containerfile_name, containerfile_artifact)
        containerfile_path = os.path.join(working_directory, containerfile_name)

        bud_cp = subprocess.run(
            [
                "podman",
                "build",
                "-f",
                containerfile_path,
                "-t",
                name,
                context_path,
                "--isolation",
                "rootless",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if bud_cp.returncode != 0:
            raise Exception(bud_cp.stderr)
        image_dir = os.path.join(working_directory, "image")
        os.makedirs(image_dir, exist_ok=True)
        push_cp = subprocess.run(
            ["podman", "push", "-f", "oci", name, "dir:{}".format(image_dir)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if push_cp.returncode != 0:
            raise Exception(push_cp.stderr)
        repository_version = add_image_from_directory_to_repository(image_dir, repository, tag)
        if isinstance(containerfile_artifact, PulpTemporaryFile):
            containerfile_artifact.delete()

    if repository_version:
        try:
            from pulpcore.plugin.serializers import RepositoryVersionSerializer

            repository_version = RepositoryVersionSerializer(
                instance=repository_version, context={"request": None}
            ).data
        except ImportError:
            pass
    return repository_version


def build_image_from_containerfile(
    containerfile_pk=None, artifacts=None, repository_pk=None, tag=None
):
    """
    DEPRECATED: this function is deprecated and will be removed in a future release.
                Keeping it for now for backward compatibility.
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
    with tempfile.TemporaryDirectory(dir=".") as working_directory:
        working_directory = os.path.abspath(working_directory)
        context_path = os.path.join(working_directory, "context")
        os.makedirs(context_path, exist_ok=True)
        for key, val in artifacts.items():
            artifact = Artifact.objects.get(pk=key)
            dest_path = os.path.join(context_path, val)
            dirs = os.path.split(dest_path)[0]
            if dirs:
                os.makedirs(dirs, exist_ok=True)
            with open(dest_path, "wb") as dest:
                shutil.copyfileobj(artifact.file, dest)

            containerfile_path = os.path.join(working_directory, "Containerfile")

        with open(containerfile_path, "wb") as dest:
            shutil.copyfileobj(containerfile.file, dest)
        bud_cp = subprocess.run(
            [
                "podman",
                "build",
                "-f",
                containerfile_path,
                "-t",
                name,
                context_path,
                "--isolation",
                "rootless",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if bud_cp.returncode != 0:
            raise Exception(bud_cp.stderr)
        image_dir = os.path.join(working_directory, "image")
        os.makedirs(image_dir, exist_ok=True)
        push_cp = subprocess.run(
            ["podman", "push", "-f", "oci", name, "dir:{}".format(image_dir)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if push_cp.returncode != 0:
            raise Exception(push_cp.stderr)
        repository_version = add_image_from_directory_to_repository(image_dir, repository, tag)

    return repository_version


def _copy_file_from_artifact(context_path, relative_path, artifact):
    dest_path = os.path.join(context_path, relative_path)
    dirs = os.path.dirname(dest_path)
    if dirs:
        os.makedirs(dirs, exist_ok=True)
    with open(dest_path, "wb") as dest:
        shutil.copyfileobj(artifact.file, dest)

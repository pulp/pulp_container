import pytest

from tempfile import NamedTemporaryFile

from pulpcore.tests.functional.utils import PulpTaskError
from pulp_container.constants import MANIFEST_TYPE


@pytest.fixture
def containerfile_name():
    """A fixture for a basic container file used for building images."""
    with NamedTemporaryFile() as containerfile:
        containerfile.write(
            b"""FROM quay.io/quay/busybox:latest
# Copy a file using COPY statement. Use the relative path specified in the 'artifacts' parameter.
COPY foo/bar/example.txt /tmp/inside-image.txt
# Print the content of the file when the container starts
CMD ["cat", "/tmp/inside-image.txt"]"""
        )
        containerfile.flush()
        yield containerfile.name


@pytest.fixture
def populated_file_repo(
    containerfile_name,
    file_bindings,
    file_repo,
    tmp_path_factory,
    monitor_task,
):
    filename = tmp_path_factory.mktemp("fixtures") / "example.txt"
    filename.write_bytes(b"test content")
    upload_task = file_bindings.ContentFilesApi.create(
        relative_path="foo/bar/example.txt", file=str(filename), repository=file_repo.pulp_href
    ).task
    monitor_task(upload_task)

    upload_task = file_bindings.ContentFilesApi.create(
        relative_path="Containerfile", file=containerfile_name, repository=file_repo.pulp_href
    ).task
    monitor_task(upload_task)

    return file_repo


@pytest.fixture
def build_image(container_bindings, monitor_task):
    def _build_image(repository, containerfile=None, containerfile_name=None, build_context=None):
        build_response = container_bindings.RepositoriesContainerApi.build_image(
            container_container_repository_href=repository,
            containerfile=containerfile,
            containerfile_name=containerfile_name or "",
            build_context=build_context or "",
        )
        monitor_task(build_response.task)

    return _build_image


def test_build_image_with_uploaded_containerfile(
    build_image,
    check_manifest_fields,
    containerfile_name,
    container_distribution_factory,
    container_repo,
    populated_file_repo,
    delete_orphans_pre,
    local_registry,
    full_path,
):
    """Test build an OCI image from a file repository_version."""
    build_image(
        repository=container_repo.pulp_href,
        containerfile=containerfile_name,
        build_context=f"{populated_file_repo.pulp_href}versions/1/",
    )

    distribution = container_distribution_factory(repository=container_repo.pulp_href)

    local_registry.pull(full_path(distribution))
    image = local_registry.inspect(full_path(distribution))
    assert image[0]["Config"]["Cmd"] == ["cat", "/tmp/inside-image.txt"]
    assert check_manifest_fields(
        manifest_filters={"digest": image[0]["Digest"]}, fields={"type": MANIFEST_TYPE.IMAGE}
    )


def test_build_image_from_repo_version_with_anon_user(
    build_image,
    containerfile_name,
    container_repo,
    delete_orphans_pre,
    populated_file_repo,
    gen_user,
    container_bindings,
):
    """Test if a user without permission to file repo can build an OCI image."""
    user_helpless = gen_user(
        model_roles=[
            "container.containerdistribution_collaborator",
            "container.containerrepository_content_manager",
        ]
    )
    with user_helpless, pytest.raises(container_bindings.ApiException):
        build_image(
            container_repo.pulp_href,
            containerfile_name,
            build_context=f"{populated_file_repo.pulp_href}versions/1/",
        )


def test_build_image_from_repo_version_with_creator_user(
    build_image,
    containerfile_name,
    container_repo,
    delete_orphans_pre,
    populated_file_repo,
    gen_user,
):
    """Test if a user (with the expected permissions) can build an OCI image."""
    user = gen_user(
        object_roles=[
            ("container.containerrepository_content_manager", container_repo.pulp_href),
            ("file.filerepository_viewer", populated_file_repo.pulp_href),
        ],
    )
    with user:
        build_image(
            repository=container_repo.pulp_href,
            containerfile=containerfile_name,
            build_context=f"{populated_file_repo.pulp_href}versions/1/",
        )


def test_build_image_without_containerfile(
    build_image,
    container_bindings,
    container_repo,
    populated_file_repo,
):
    """Test build an OCI image without a containerfile"""
    with pytest.raises(container_bindings.ApiException):
        build_image(
            repository=container_repo.pulp_href,
            build_context=f"{populated_file_repo.pulp_href}versions/2/",
        )


def test_build_image_without_expected_files(
    build_image,
    containerfile_name,
    container_repo,
):
    """
    Test build an OCI image without the expected files (build_context) defined in the Containerfile
    """
    with pytest.raises(PulpTaskError):
        build_image(
            repository=container_repo.pulp_href,
            containerfile=containerfile_name,
        )


def test_build_image_from_containerfile_name(
    build_image,
    container_distribution_factory,
    container_repo,
    delete_orphans_pre,
    local_registry,
    populated_file_repo,
    full_path,
):
    """Test build an OCI image with a containerfile from build_context."""
    build_image(
        repository=container_repo.pulp_href,
        containerfile_name="Containerfile",
        build_context=f"{populated_file_repo.pulp_href}versions/2/",
    )

    distribution = container_distribution_factory(repository=container_repo.pulp_href)

    local_registry.pull(full_path(distribution))
    image = local_registry.inspect(full_path(distribution))
    assert image[0]["Config"]["Cmd"] == ["cat", "/tmp/inside-image.txt"]


def test_invalid_containerfile_from_build_context(
    build_image,
    container_bindings,
    container_repo,
    populated_file_repo,
):
    """Test with a non-existing Containerfile in file repository."""
    with pytest.raises(container_bindings.ApiException) as e:
        build_image(
            repository=container_repo.pulp_href,
            containerfile_name="Non_existing_file",
            build_context=f"{populated_file_repo.pulp_href}versions/2/",
        )
    assert e.value.status == 400
    assert "Could not find the Containerfile" in e.value.body


def test_without_build_context(
    build_image,
    check_manifest_arch_os_size,
    container_distribution_factory,
    container_bindings,
    container_repo,
    local_registry,
    full_path,
):
    """Test build with only a Containerfile (no additional files)"""

    def containerfile_without_context_files():
        with NamedTemporaryFile() as containerfile:
            containerfile.write(
                b"""FROM quay.io/quay/busybox:latest
# Print the content of the file when the container starts
CMD ["ls", "/"]"""
            )
            containerfile.flush()
            yield containerfile.name

    containerfile_name = containerfile_without_context_files()
    build_image(
        repository=container_repo.pulp_href,
        containerfile=next(containerfile_name),
    )

    distribution = container_distribution_factory(repository=container_repo.pulp_href)

    local_registry.pull(full_path(distribution))
    image = local_registry.inspect(full_path(distribution))
    assert image[0]["Config"]["Cmd"] == ["ls", "/"]
    manifest = container_bindings.ContentManifestsApi.list(digest=image[0]["Digest"])
    check_manifest_arch_os_size(manifest)

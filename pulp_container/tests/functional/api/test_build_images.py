import pytest

from tempfile import NamedTemporaryFile

from pulp_smash.pulp3.utils import (
    gen_distribution,
    gen_repo,
)
from pulp_smash.pulp3.bindings import monitor_task

from pulpcore.client.pulp_container import (
    ContainerContainerDistribution,
    ContainerContainerRepository,
)


@pytest.fixture
def containerfile_name():
    """A fixture for a basic container file used for building images."""
    with NamedTemporaryFile() as containerfile:
        containerfile.write(
            b"""FROM busybox:latest
# Copy a file using COPY statement. Use the relative path specified in the 'artifacts' parameter.
COPY foo/bar/example.txt /tmp/inside-image.txt
# Print the content of the file when the container starts
CMD ["cat", "/tmp/inside-image.txt"]"""
        )
        containerfile.flush()
        yield containerfile.name


def test_build_image(
    pulpcore_bindings,
    container_repository_api,
    container_distribution_api,
    gen_object_with_cleanup,
    containerfile_name,
    local_registry,
):
    """Test if a user can build an OCI image."""
    with NamedTemporaryFile() as text_file:
        text_file.write(b"some text")
        text_file.flush()
        artifact = gen_object_with_cleanup(pulpcore_bindings.ArtifactsApi, text_file.name)

    repository = gen_object_with_cleanup(
        container_repository_api, ContainerContainerRepository(**gen_repo())
    )

    artifacts = '{{"{}": "foo/bar/example.txt"}}'.format(artifact.pulp_href)
    build_response = container_repository_api.build_image(
        repository.pulp_href, containerfile=containerfile_name, artifacts=artifacts
    )
    monitor_task(build_response.task)

    distribution = gen_object_with_cleanup(
        container_distribution_api,
        ContainerContainerDistribution(**gen_distribution(repository=repository.pulp_href)),
    )

    local_registry.pull(distribution.base_path)
    image = local_registry.inspect(distribution.base_path)
    assert image[0]["Config"]["Cmd"] == ["cat", "/tmp/inside-image.txt"]

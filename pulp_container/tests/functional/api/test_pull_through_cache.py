import time
import subprocess
import pytest

from uuid import uuid4

from pulp_container.tests.functional.constants import (
    REGISTRY_V2,
    REGISTRY_V2_FEED_URL,
    PULP_HELLO_WORLD_REPO,
    PULP_FIXTURE_1,
)


@pytest.fixture
def pull_through_distribution(
    gen_object_with_cleanup,
    container_pull_through_remote_api,
    container_pull_through_distribution_api,
):
    remote = gen_object_with_cleanup(
        container_pull_through_remote_api,
        {"name": str(uuid4()), "url": REGISTRY_V2_FEED_URL},
    )
    distribution = gen_object_with_cleanup(
        container_pull_through_distribution_api,
        {"name": str(uuid4()), "base_path": str(uuid4()), "remote": remote.pulp_href},
    )
    return distribution


@pytest.fixture
def pull_and_verify(
    add_to_cleanup,
    container_pull_through_distribution_api,
    container_distribution_api,
    container_repository_api,
    container_remote_api,
    container_tag_api,
    registry_client,
    local_registry,
):
    def _pull_and_verify(images, pull_through_distribution):
        tags_to_verify = []
        for version, image_path in enumerate(images, start=1):
            remote_image_path = f"{REGISTRY_V2}/{image_path}"
            local_image_path = f"{pull_through_distribution.base_path}/{image_path}"

            # 1. pull remote content through the pull-through distribution
            local_registry.pull(local_image_path)
            local_image = local_registry.inspect(local_image_path)

            # when the client pulls the image, a repository, distribution, and remote is created in
            # the background; therefore, scheduling the cleanup for these entities is necessary
            path, tag = local_image_path.split(":")
            tags_to_verify.append(tag)
            repository = container_repository_api.list(name=path).results[0]
            add_to_cleanup(container_repository_api, repository.pulp_href)
            remote = container_remote_api.list(name=path).results[0]
            add_to_cleanup(container_remote_api, remote.pulp_href)
            distribution = container_distribution_api.list(name=path).results[0]
            add_to_cleanup(container_distribution_api, distribution.pulp_href)

            pull_through_distribution = container_pull_through_distribution_api.list(
                name=pull_through_distribution.name
            ).results[0]
            assert [distribution.pulp_href] == pull_through_distribution.distributions

            # 2. verify if the pulled content is the same as on the remote
            registry_client.pull(remote_image_path)
            remote_image = registry_client.inspect(remote_image_path)
            assert local_image[0]["Id"] == remote_image[0]["Id"]

            # 3. check if the repository version has changed
            for _ in range(5):
                repository = container_repository_api.list(name=path).results[0]
                if f"{repository.pulp_href}versions/{version}/" == repository.latest_version_href:
                    break

                # there might be still the saving process running in the background
                time.sleep(1)
            else:
                assert False, "The repository was not updated with the cached content."

            # 4. test if pulling the same content twice does not raise any error
            local_registry.pull(local_image_path)

            # 5. assert the cached tags
            tags = container_tag_api.list(repository_version=repository.latest_version_href).results
            assert sorted(tags_to_verify) == sorted([tag.name for tag in tags])

    return _pull_and_verify


def test_manifest_list_pull(delete_orphans_pre, pull_through_distribution, pull_and_verify):
    images = [f"{PULP_HELLO_WORLD_REPO}:latest", f"{PULP_HELLO_WORLD_REPO}:linux"]
    pull_and_verify(images, pull_through_distribution)


def test_manifest_pull(delete_orphans_pre, pull_through_distribution, pull_and_verify):
    images = [f"{PULP_FIXTURE_1}:manifest_a", f"{PULP_FIXTURE_1}:manifest_b"]
    pull_and_verify(images, pull_through_distribution)


def test_conflicting_names_and_paths(
    container_remote_api,
    container_remote_factory,
    container_repository_api,
    container_repository_factory,
    container_distribution_api,
    pull_through_distribution,
    gen_object_with_cleanup,
    local_registry,
    monitor_task,
):
    local_image_path = f"{pull_through_distribution.base_path}/{str(uuid4())}"

    remote = container_remote_factory(name=local_image_path)
    # a remote with the same name but a different URL already exists
    with pytest.raises(subprocess.CalledProcessError):
        local_registry.pull(local_image_path)
    monitor_task(container_remote_api.delete(remote.pulp_href).task)

    assert 0 == len(container_repository_api.list(name=local_image_path).results)
    assert 0 == len(container_distribution_api.list(name=local_image_path).results)

    repository = container_repository_factory(name=local_image_path)
    # a repository with the same name but a different retain configuration already exists
    with pytest.raises(subprocess.CalledProcessError):
        local_registry.pull(local_image_path)
    monitor_task(container_repository_api.delete(repository.pulp_href).task)

    assert 0 == len(container_remote_api.list(name=local_image_path).results)
    assert 0 == len(container_distribution_api.list(name=local_image_path).results)

    data = {"name": local_image_path, "base_path": local_image_path}
    distribution = gen_object_with_cleanup(container_distribution_api, data)
    # a distribution with the same name but different foreign keys already exists
    with pytest.raises(subprocess.CalledProcessError):
        local_registry.pull(local_image_path)
    monitor_task(container_distribution_api.delete(distribution.pulp_href).task)

    assert 0 == len(container_repository_api.list(name=local_image_path).results)
    assert 0 == len(container_remote_api.list(name=local_image_path).results)

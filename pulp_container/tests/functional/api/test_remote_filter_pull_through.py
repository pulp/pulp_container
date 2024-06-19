import pytest
import subprocess

from pulp_container.tests.functional.constants import (
    REGISTRY_V2,
    PULP_HELLO_WORLD_REPO,
    PULP_FIXTURE_1,
)


@pytest.fixture
def pull_and_verify(
    capfd,
    local_registry,
    registry_client,
):
    def _pull_and_verify(images, pull_through_distribution, includes, excludes, expected):
        distr = pull_through_distribution(includes, excludes)
        for image_path in images:
            remote_image_path = f"{REGISTRY_V2}/{image_path}"
            local_image_path = f"{distr.base_path}/{image_path}"

            if image_path not in expected:
                with pytest.raises(subprocess.CalledProcessError):
                    local_registry.pull(local_image_path)
                assert "Repository not found" in capfd.readouterr().err
            else:
                local_registry.pull(local_image_path)
                local_image = local_registry.inspect(local_image_path)
                registry_client.pull(remote_image_path)
                remote_image = registry_client.inspect(remote_image_path)
                assert local_image[0]["Id"] == remote_image[0]["Id"]

    return _pull_and_verify


@pytest.mark.parametrize(
    "images, includes, excludes, expected",
    [
        (
            [f"{PULP_FIXTURE_1}:manifest_a", f"{PULP_FIXTURE_1}:manifest_b"],
            None,
            [],
            [f"{PULP_FIXTURE_1}:manifest_a", f"{PULP_FIXTURE_1}:manifest_b"],
        ),
        ([f"{PULP_FIXTURE_1}:manifest_a", f"{PULP_FIXTURE_1}:manifest_b"], [], ["pulp*"], []),
        (
            [f"{PULP_FIXTURE_1}:manifest_a", f"{PULP_FIXTURE_1}:manifest_b"],
            [],
            ["pulp/test-fixture-1"],
            [],
        ),
        (
            [
                f"{PULP_FIXTURE_1}:manifest_a",
                f"{PULP_FIXTURE_1}:manifest_b",
                f"{PULP_HELLO_WORLD_REPO}:linux",
            ],
            ["*hello*"],
            ["*fixture*"],
            [f"{PULP_HELLO_WORLD_REPO}:linux"],
        ),
        (
            ["custom_namespace/custom_repo:latest"],
            ["*pulp*"],
            None,
            [],
        ),
    ],
)
def test_includes_excludes_filter(
    images,
    includes,
    excludes,
    expected,
    pull_through_distribution,
    pull_and_verify,
    delete_orphans_pre,
):
    pull_and_verify(images, pull_through_distribution, includes, excludes, expected)

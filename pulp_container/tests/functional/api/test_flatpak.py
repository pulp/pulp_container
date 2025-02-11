"""Tests that verify Flatpak support"""

import pytest
import subprocess

from pulp_container.tests.functional.constants import REGISTRY_V2


pytestmark = pytest.mark.skip(reason="TLS is broken currently. TODO: Fix")


def run_flatpak_commands(host):
    # Install flatpak:
    subprocess.check_call(
        [
            "flatpak",
            "--user",
            "remote-add",
            "pulptest",
            "oci+" + host,
        ]
    )
    # See <https://pagure.io/fedora-lorax-templates/c/cc1155372046baa58f9d2cc27a9e5473bf05a3fb>
    # "lorax-embed-flatpaks.tmpl: Run the flatpak-install under dbus-run-session" for the need for
    # dbus-run-session to avoid "error: Cannot autolaunch D-Bus without X11 $DISPLAY":
    subprocess.check_call(
        [
            "dbus-run-session",
            "flatpak",
            "--user",
            "install",
            "--noninteractive",
            "pulptest",
            "net.fishsoup.Hello",
        ]
    )

    # Clean up flatpak:
    subprocess.run(
        [
            "flatpak",
            "--user",
            "uninstall",
            "--noninteractive",
            "net.fishsoup.Hello",
        ]
    )
    subprocess.run(
        [
            "flatpak",
            "--user",
            "uninstall",
            "--noninteractive",
            "net.fishsoup.BusyBoxPlatform",
        ]
    )
    subprocess.run(["flatpak", "--user", "remote-delete", "pulptest"])


def test_flatpak_install(
    add_to_cleanup,
    registry_client,
    local_registry,
    container_namespace_api,
    container_push_repository_api,
    container_tag_api,
    container_manifest_api,
    pulp_settings,
    bindings_cfg,
):
    if not pulp_settings.FLATPAK_INDEX:
        pytest.skip("This test requires FLATPAK_INDEX to be enabled")

    image_path1 = f"{REGISTRY_V2}/pulp/oci-net.fishsoup.busyboxplatform:latest"
    registry_client.pull(image_path1)
    local_registry.tag_and_push(image_path1, "pulptest/oci-net.fishsoup.busyboxplatform:latest")
    image_path2 = f"{REGISTRY_V2}/pulp/oci-net.fishsoup.hello:latest"
    registry_client.pull(image_path2)
    local_registry.tag_and_push(image_path2, "pulptest/oci-net.fishsoup.hello:latest")
    namespace = container_namespace_api.list(name="pulptest").results[0]
    add_to_cleanup(container_namespace_api, namespace.pulp_href)

    repo = container_push_repository_api.list(name="pulptest/oci-net.fishsoup.hello").results[0]
    tag = container_tag_api.list(repository_version=repo.latest_version_href).results[0]
    manifest = container_manifest_api.read(tag.tagged_manifest)

    assert manifest.is_flatpak
    assert not manifest.is_bootable

    run_flatpak_commands(bindings_cfg.host)


def test_flatpak_on_demand(
    container_tag_api,
    container_manifest_api,
    container_repository_factory,
    container_remote_factory,
    container_sync,
    container_distribution_factory,
    container_namespace_api,
    pulpcore_bindings,
    monitor_task,
    add_to_cleanup,
    pulp_settings,
    bindings_cfg,
):
    if not pulp_settings.FLATPAK_INDEX:
        pytest.skip("This test requires FLATPAK_INDEX to be enabled")

    # Set up repositories with immediate sync
    remote1 = container_remote_factory(
        upstream_name="pulp/oci-net.fishsoup.busyboxplatform", include_tags=["latest"]
    )
    remote2 = container_remote_factory(
        upstream_name="pulp/oci-net.fishsoup.hello", include_tags=["latest"]
    )
    repo1 = container_repository_factory(remote=remote1.pulp_href)
    repo2 = container_repository_factory(remote=remote2.pulp_href)
    container_sync(repo1)
    container_sync(repo2)
    container_distribution_factory(
        base_path="pulptest/oci-net.fishsoup.busyboxplatform", repository=repo1.pulp_href
    )
    container_distribution_factory(
        base_path="pulptest/oci-net.fishsoup.hello", repository=repo2.pulp_href
    )
    namespace = container_namespace_api.list(name="pulptest").results[0]
    add_to_cleanup(container_namespace_api, namespace.pulp_href)

    # Assert the repos were set up correctly
    tag = container_tag_api.list(repository_version=f"{repo2.versions_href}1/").results[0]
    manifest = container_manifest_api.read(tag.tagged_manifest)
    assert manifest.is_flatpak
    assert not manifest.is_bootable

    # reclaim disk space to turn the manifests + config-blogs into on-demand
    reclaim_response = pulpcore_bindings.RepositoriesReclaimSpaceApi.reclaim(
        {"repo_hrefs": [repo1.pulp_href, repo2.pulp_href]}
    )
    monitor_task(reclaim_response.task)

    run_flatpak_commands(bindings_cfg.host)

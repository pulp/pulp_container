"""Tests that verify Flatpak support"""

import pytest
import subprocess

from django.conf import settings

from pulp_container.tests.functional.constants import REGISTRY_V2


def test_flatpak_install(
    add_to_cleanup,
    registry_client,
    local_registry,
    container_namespace_api,
    container_push_repository_api,
    container_tag_api,
    container_manifest_api,
):
    if not settings.FLATPAK_INDEX:
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

    # Install flatpak:
    subprocess.check_call(
        [
            "flatpak",
            "--user",
            "remote-add",
            "pulptest",
            "oci+" + settings.CONTENT_ORIGIN,
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

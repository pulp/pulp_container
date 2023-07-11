"""Tests that verify Flatpak support"""
import subprocess

from django.conf import settings


def test_flatpak_install(
    add_to_cleanup,
    registry_client,
    local_registry,
    container_namespace_api,
):
    image_path1 = "registry.fedoraproject.org/f38/flatpak-kde5-runtime:latest"
    registry_client.pull(image_path1)
    local_registry.tag_and_push(image_path1, "pulptest/f38/flatpak-kde5-runtime:latest")
    image_path2 = "registry.fedoraproject.org/kcolorchooser:latest"
    registry_client.pull(image_path2)
    local_registry.tag_and_push(image_path2, "pulptest/kcolorchooser:latest")
    subprocess.check_call(["flatpak", "remote-add", "pulptest", "oci+" + settings.CONTENT_ORIGIN])
    # See <https://pagure.io/fedora-lorax-templates/c/cc1155372046baa58f9d2cc27a9e5473bf05a3fb>
    # "lorax-embed-flatpaks.tmpl: Run the flatpak-install under dbus-run-session" for the need for
    # dbus-run-session to avoid "error: Cannot autolaunch D-Bus without X11 $DISPLAY":
    subprocess.check_call(
        [
            "dbus-run-session",
            "flatpak",
            "install",
            "--noninteractive",
            "pulptest",
            "org.kde.kcolorchooser",
        ]
    )

    # Cleanup:
    subprocess.run(["flatpak", "uninstall", "--noninteractive", "org.kde.kcolorchooser"])
    subprocess.run(["flatpak", "uninstall", "--noninteractive", "org.fedoraproject.KDE5Platform"])
    subprocess.run(["flatpak", "remote-delete", "pulptest"])
    namespace = container_namespace_api.list(name="pulptest").results[0]
    add_to_cleanup(container_namespace_api, namespace.pulp_href)

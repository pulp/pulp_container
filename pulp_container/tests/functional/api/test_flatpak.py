"""Tests that verify Flatpak support"""

import os

import pytest
import subprocess

from pulp_container.tests.functional.constants import REGISTRY_V2

PULP_CA_CERT = "/etc/pulp/certs/pulp_webserver.crt"


def _ensure_system_trust():
    """Add the Pulp CA cert to the system trust store so flatpak can verify TLS.

    On RHEL 9, both flatpak (via GLib/libsoup) and Python's OpenSSL resolve trust
    through p11-kit.  The only reliable way to make flatpak accept the self-signed
    Pulp webserver cert is to register it as a trust anchor.  This is safe to call
    after the certifi patching in script.sh because `trust anchor` only *adds* to
    the trust store.
    """
    anchor = "/etc/pki/ca-trust/source/anchors/pulp_webserver.crt"
    if os.path.exists(PULP_CA_CERT) and not os.path.exists(anchor):
        subprocess.check_call(["sudo", "cp", PULP_CA_CERT, anchor])
        subprocess.check_call(["sudo", "update-ca-trust"])
        # Re-patch certifi in case update-ca-trust regenerated the bundle it points to.
        result = subprocess.run(
            ["python3", "-c", "import certifi; print(certifi.where())"],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            certifi_path = result.stdout.strip()
            subprocess.run(
                ["sudo", "bash", "-c", f"cat {PULP_CA_CERT} >> '{certifi_path}'"],
                check=False,
            )


def run_flatpak_commands(host):
    _ensure_system_trust()

    # Remove any leftover remote from a previous failed run before starting.
    subprocess.run(["flatpak", "--user", "remote-delete", "--force", "pulptest"], check=False)

    subprocess.check_call(
        [
            "flatpak",
            "--user",
            "remote-add",
            "pulptest",
            "oci+" + host,
        ]
    )

    try:
        # See <https://pagure.io/fedora-lorax-templates/c/cc1155372046baa58f9d2cc27a9e5473bf05a3fb>
        # "lorax-embed-flatpaks.tmpl: Run the flatpak-install under dbus-run-session" for the need
        # for dbus-run-session to avoid "error: Cannot autolaunch D-Bus without X11 $DISPLAY":
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
    finally:
        # Clean up flatpak — runs even if install fails so the next test starts clean.
        subprocess.run(
            [
                "flatpak",
                "--user",
                "uninstall",
                "--noninteractive",
                "net.fishsoup.Hello",
            ],
        )
        subprocess.run(
            [
                "flatpak",
                "--user",
                "uninstall",
                "--noninteractive",
                "net.fishsoup.BusyBoxPlatform",
            ],
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
    full_path,
):
    if not pulp_settings.FLATPAK_INDEX:
        pytest.skip("This test requires FLATPAK_INDEX to be enabled")

    image_path1 = f"{REGISTRY_V2}/pulp/oci-net.fishsoup.busyboxplatform:latest"
    registry_client.pull(image_path1)
    local_registry.tag_and_push(
        image_path1, full_path("pulptest/oci-net.fishsoup.busyboxplatform") + ":latest"
    )
    image_path2 = f"{REGISTRY_V2}/pulp/oci-net.fishsoup.hello:latest"
    registry_client.pull(image_path2)
    local_registry.tag_and_push(
        image_path2, full_path("pulptest/oci-net.fishsoup.hello") + ":latest"
    )
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

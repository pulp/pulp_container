import json
import os
import stat
import pytest
import requests
import subprocess

from contextlib import contextmanager, suppress
from urllib.parse import urljoin, urlparse
from uuid import uuid4

from pulpcore.tests.functional.utils import BindingsNamespace

from pulp_container.tests.functional.utils import (
    AuthenticationHeaderQueries,
    BearerTokenAuth,
)

from pulp_container.tests.functional.constants import REGISTRY_V2_FEED_URL, PULP_HELLO_WORLD_REPO


def gen_container_remote(url=REGISTRY_V2_FEED_URL, **kwargs):
    """Return a semi-random dict for use in creating a container Remote.

    :param url: The URL of an external content source.
    """

    data = {"name": str(uuid4()), "url": url}
    data["upstream_name"] = kwargs.pop("upstream_name", PULP_HELLO_WORLD_REPO)
    data.update(kwargs)
    return data


class RegistryClient:
    """A container registry client on a test runner machine."""

    NAME = "podman"

    def __init__(self, tls_verify):
        self._name = None

        self.pull = lambda *args: self._dispatch_command("pull", *args, tls_verify)
        self.push = lambda *args: self._dispatch_command("push", *args, tls_verify)
        self.manifest_push = lambda *args: self._dispatch_command(
            "manifest", "push", *args, tls_verify
        )
        self.login = lambda *args: self._dispatch_command("login", *args, tls_verify)

        self.logout = lambda *args: self._dispatch_command("logout", *args)
        self.inspect = lambda *args: self._dispatch_command("inspect", *args)
        self.import_ = lambda *args: self._dispatch_command("import", *args)
        self.images = lambda *args: self._dispatch_command("images", "--format", "json", *args)
        self.rmi = lambda *args: self._dispatch_command("rmi", *args)
        self.tag = lambda *args: self._dispatch_command("tag", *args)

    @property
    def name(self):
        if not self._name:
            self._name = self._get_registry_client()
        return self._name

    def raise_if_unsupported(self, exc, message="Unsupported registry client"):
        try:
            self.name
        except RuntimeError:
            raise exc(message)

    @contextmanager
    def set_env(self, **environ):
        old_environ = os.environ.copy()
        os.environ.update(environ)
        try:
            yield
        finally:
            os.environ.clear()
            os.environ.update(old_environ)

    def _get_registry_client(self):
        if subprocess.run(("which", self.NAME)).returncode == 0:
            return self.NAME

        raise RuntimeError("The client '{}' does not appear to be installed.".format(self.NAME))

    def _dispatch_command(self, command, *args):
        cmd = (self.name, command) + tuple(args)
        result = subprocess.check_output(cmd).decode()
        try:
            # most client responses are JSONable
            return json.loads(result)
        except json.JSONDecodeError:
            return result


@pytest.fixture(scope="session")
def tls_verify(bindings_cfg):
    scheme = urlparse(bindings_cfg.host).scheme
    return "--tls-verify=false" if scheme == "http" else "--tls-verify=true"


@pytest.fixture(scope="session")
def registry_client(tls_verify):
    """Fixture for a container registry client."""
    registry = RegistryClient(tls_verify)
    try:
        registry.raise_if_unsupported(ValueError, "Tests require podman/docker")
    except ValueError:
        pytest.Skip("Tests require podman/docker")

    return registry


@pytest.fixture()
def local_registry(request, _local_registry):
    """Local registry with authentication."""

    # This check only works, if the fixture is scoped to the test
    if request.node.get_closest_marker("parallel") is not None:
        raise pytest.UsageError("This test is not suitable to be marked parallel.")

    return _local_registry


@pytest.fixture(scope="session")
def _local_registry(bindings_cfg, registry_client, pulp_settings):
    """Local registry with authentication. Session scoped."""

    registry_name = urlparse(bindings_cfg.host).netloc

    class _LocalRegistry:
        @property
        def name(self):
            return registry_name

        @staticmethod
        def get_response(method, path, **kwargs):
            """Return a response while dealing with token authentication."""
            url = urljoin(bindings_cfg.host, path)

            basic_auth = (bindings_cfg.username, bindings_cfg.password)
            if pulp_settings.TOKEN_AUTH_DISABLED:
                auth = basic_auth
            else:
                with pytest.raises(requests.HTTPError):
                    response = requests.request(method, url, auth=basic_auth, **kwargs)
                    response.raise_for_status()
                assert response.status_code == 401

                authenticate_header = response.headers["WWW-Authenticate"]
                queries = AuthenticationHeaderQueries(authenticate_header)

                content_response = requests.get(
                    queries.realm,
                    params={"service": queries.service, "scope": queries.scopes},
                    auth=basic_auth,
                )
                content_response.raise_for_status()
                token = content_response.json()["token"]
                auth = BearerTokenAuth(token)

            return requests.request(method, url, auth=auth, **kwargs), auth

        @staticmethod
        def _dispatch_command(*args):
            if bindings_cfg.username is not None:
                registry_client.login(
                    "-u", bindings_cfg.username, "-p", bindings_cfg.password, registry_name
                )
            else:
                registry_client.logout(registry_name)
            try:
                registry_client._dispatch_command(*args)
            finally:
                registry_client.logout(registry_name)

        @staticmethod
        def pull(image_path):
            if bindings_cfg.username is not None:
                registry_client.login(
                    "-u", bindings_cfg.username, "-p", bindings_cfg.password, registry_name
                )

                try:
                    registry_client.pull("/".join([registry_name, image_path]))
                finally:
                    registry_client.logout(registry_name)
            else:
                with suppress(subprocess.CalledProcessError):
                    registry_client.logout(registry_name)

                registry_client.pull("/".join([registry_name, image_path]))

        @staticmethod
        def tag_and_push(image_path, local_url, *args):
            local_image_path = "/".join([registry_name, local_url])
            registry_client.tag(image_path, local_image_path)
            if bindings_cfg.username is not None:
                registry_client.login(
                    "-u", bindings_cfg.username, "-p", bindings_cfg.password, registry_name
                )
            else:
                registry_client.logout(registry_name)
            try:
                registry_client.push(local_image_path, *args)
            finally:
                # Untag local copy
                registry_client.rmi(local_image_path)
                registry_client.logout(registry_name)

        @staticmethod
        def manifest_push(tag, image_path, *args):
            local_image_path = "/".join([registry_name, image_path])
            if bindings_cfg.username is not None:
                registry_client.login(
                    "-u", bindings_cfg.username, "-p", bindings_cfg.password, registry_name
                )
            else:
                registry_client.logout(registry_name)
            try:
                registry_client.manifest_push(tag, local_image_path, *args)
            finally:
                registry_client.logout(registry_name)

        @staticmethod
        def inspect(local_url):
            local_image_path = "/".join([registry_name, local_url])
            return registry_client.inspect(local_image_path)

    return _LocalRegistry()


@pytest.fixture(scope="session")
def signing_script_filename(signing_gpg_homedir_path):
    """A fixture for a script that is suited for signing manifests."""
    raw_script = (
        "#!/usr/bin/env bash",
        "",
        "# use the side channel to set the GNUPGHOME variable",
        f'export GNUPGHOME="{signing_gpg_homedir_path}"',
        "",
        "MANIFEST_PATH=$1",
        'FINGEPRINT="$PULP_SIGNING_KEY_FINGERPRINT"',
        "",
        "skopeo standalone-sign $MANIFEST_PATH $REFERENCE $FINGEPRINT -o $SIG_PATH",
        "",
        "STATUS=$?",
        "if [ $STATUS -eq 0 ]; then",
        '   echo {\\"signature_path\\": \\"$SIG_PATH\\"}',
        "else",
        "   exit $STATUS",
        "fi",
        "",
    )

    with open(os.path.join(signing_gpg_homedir_path, "bash-script.sh"), "w") as f:
        f.write("\n".join(raw_script))

    return f.name


@pytest.fixture
def container_signing_service(
    pulpcore_bindings,
    signing_gpg_metadata,
    signing_script_filename,
):
    """A fixture for a signing service."""
    st = os.stat(signing_script_filename)
    os.chmod(signing_script_filename, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    gpg, fingerprint, keyid = signing_gpg_metadata

    service_name = str(uuid4())
    cmd = (
        "pulpcore-manager",
        "add-signing-service",
        service_name,
        signing_script_filename,
        keyid,
        "--class",
        "container:ManifestSigningService",
        "--gnupghome",
        gpg.gnupghome,
    )

    subprocess.check_output(cmd)

    signing_service = pulpcore_bindings.SigningServicesApi.list(name=service_name).results[0]
    assert signing_service.pubkey_fingerprint == fingerprint
    assert signing_service.public_key == gpg.export_keys(keyid)

    yield signing_service

    cmd = (
        "pulpcore-manager",
        "shell",
        "-c",
        "from pulpcore.app.models import SigningService;"
        f"SigningService.objects.filter(name='{service_name}').delete()",
    )

    subprocess.check_output(cmd)


# Bindings API Fixtures


@pytest.fixture(scope="session")
def container_bindings(_api_client_set, bindings_cfg):
    """
    A namespace providing preconfigured pulp_python api clients.

    e.g. `python_bindings.RepositoriesPythonApi.list()`.
    """
    from pulpcore.client import pulp_container as container_bindings_module

    api_client = container_bindings_module.ApiClient(bindings_cfg)
    _api_client_set.add(api_client)
    yield BindingsNamespace(container_bindings_module, api_client)
    _api_client_set.remove(api_client)


# TODO: Remove all of these once rewrite is complete
@pytest.fixture(scope="session")
def container_namespace_api(container_bindings):
    """Container namespace API fixture."""
    return container_bindings.PulpContainerNamespacesApi


@pytest.fixture(scope="session")
def container_remote_api(container_bindings):
    """Container remote API fixture."""
    return container_bindings.RemotesContainerApi


@pytest.fixture(scope="session")
def container_pull_through_remote_api(container_bindings):
    """Pull through cache container remote API fixture."""
    return container_bindings.RemotesPullThroughApi


@pytest.fixture(scope="session")
def container_repository_api(container_bindings):
    """Container repository API fixture."""
    return container_bindings.RepositoriesContainerApi


@pytest.fixture(scope="session")
def container_repository_version_api(container_bindings):
    """Container repository version API fixture."""
    return container_bindings.RepositoriesContainerVersionsApi


@pytest.fixture(scope="session")
def container_push_repository_api(container_bindings):
    """Container push repository API fixture."""
    return container_bindings.RepositoriesContainerPushApi


@pytest.fixture(scope="session")
def container_push_repository_version_api(container_bindings):
    """Container repository version API fixture."""
    return container_bindings.RepositoriesContainerPushVersionsApi


@pytest.fixture(scope="session")
def container_distribution_api(container_bindings):
    """Container distribution API fixture."""
    return container_bindings.DistributionsContainerApi


@pytest.fixture(scope="session")
def container_pull_through_distribution_api(container_bindings):
    """Pull through cache distribution API Fixture."""
    return container_bindings.DistributionsPullThroughApi


@pytest.fixture(scope="session")
def container_tag_api(container_bindings):
    """Container tag API fixture."""
    return container_bindings.ContentTagsApi


@pytest.fixture(scope="session")
def container_manifest_api(container_bindings):
    """Container manifest API fixture."""
    return container_bindings.ContentManifestsApi


@pytest.fixture(scope="session")
def container_blob_api(container_bindings):
    """Container blob API fixture."""
    return container_bindings.ContentBlobsApi


@pytest.fixture(scope="session")
def container_signature_api(container_bindings):
    """Container image signature API fixture."""
    return container_bindings.ContentSignaturesApi


@pytest.fixture(scope="class")
def container_repository_factory(container_bindings, gen_object_with_cleanup):
    def _container_repository_factory(**body):
        repository = {"name": str(uuid4())}
        kwargs = {}
        if "pulp_domain" in body:
            kwargs["pulp_domain"] = body.pop("pulp_domain")
        if body:
            repository.update(body)
        return gen_object_with_cleanup(
            container_bindings.RepositoriesContainerApi, repository, **kwargs
        )

    return _container_repository_factory


@pytest.fixture
def container_repo(container_repository_factory):
    return container_repository_factory()


@pytest.fixture(scope="class")
def container_remote_factory(container_bindings, gen_object_with_cleanup):
    def _container_remote_factory(url=REGISTRY_V2_FEED_URL, **body):
        kwargs = {}
        if "pulp_domain" in body:
            kwargs["pulp_domain"] = body.pop("pulp_domain")
        remote = gen_container_remote(url, **body)
        return gen_object_with_cleanup(container_bindings.RemotesContainerApi, remote, **kwargs)

    return _container_remote_factory


@pytest.fixture
def container_remote(container_remote_factory):
    return container_remote_factory()


@pytest.fixture(scope="class")
def container_sync(container_bindings, monitor_task):
    def _sync(repo, remote=None):
        remote_href = remote.pulp_href if remote else repo.remote

        sync_data = {"remote": remote_href}

        sync_response = container_bindings.RepositoriesContainerApi.sync(repo.pulp_href, sync_data)
        return monitor_task(sync_response.task)

    return _sync


@pytest.fixture(scope="class")
def container_distribution_factory(container_bindings, gen_object_with_cleanup):
    def _container_distribution_factory(**body):
        distro = {"name": str(uuid4()), "base_path": str(uuid4())}
        kwargs = {}
        if "pulp_domain" in body:
            kwargs["pulp_domain"] = body.pop("pulp_domain")
        if body:
            distro.update(body)
        return gen_object_with_cleanup(
            container_bindings.DistributionsContainerApi, distro, **kwargs
        )

    return _container_distribution_factory


@pytest.fixture(scope="class")
def pull_through_distribution(
    gen_object_with_cleanup,
    container_bindings,
):
    def _pull_through_distribution(includes=None, excludes=None, private=False):
        remote = gen_object_with_cleanup(
            container_bindings.RemotesPullThroughApi,
            {
                "name": str(uuid4()),
                "url": REGISTRY_V2_FEED_URL,
                "includes": includes,
                "excludes": excludes,
            },
        )

        data = {
            "name": str(uuid4()),
            "base_path": str(uuid4()),
            "remote": remote.pulp_href,
            "private": private,
        }
        distribution = gen_object_with_cleanup(container_bindings.DistributionsPullThroughApi, data)
        return distribution

    return _pull_through_distribution


@pytest.fixture
def check_manifest_fields(container_bindings):
    def _check_manifest_fields(**kwargs):
        manifest = container_bindings.ContentManifestsApi.list(**kwargs["manifest_filters"])
        manifest = manifest.results[0]
        for key in kwargs["fields"]:
            if getattr(manifest, key) != kwargs["fields"][key]:
                return False
        return True

    return _check_manifest_fields


@pytest.fixture
def check_manifest_arch_os_size():
    def _check_manifest_arch_os_size(manifest):
        manifests = manifest.results
        assert any("amd64" in manifest.architecture for manifest in manifests)
        assert any("linux" in manifest.os for manifest in manifests)
        assert any(manifest.compressed_image_size > 0 for manifest in manifests)

    return _check_manifest_arch_os_size


@pytest.fixture(scope="session")
def full_path(pulp_settings):
    def _full_path(base_path_or_distro, pulp_domain="default"):
        if not isinstance(base_path_or_distro, str):
            pulp_domain = base_path_or_distro.pulp_href[len(pulp_settings.API_ROOT) :].split("/")[0]
            base_path_or_distro = base_path_or_distro.base_path
        if pulp_settings.DOMAIN_ENABLED:
            return f"{pulp_domain}/{base_path_or_distro}"
        return base_path_or_distro

    return _full_path

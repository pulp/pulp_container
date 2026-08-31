import json
import os
import stat
import subprocess
from contextlib import contextmanager, suppress
from types import SimpleNamespace
from urllib.parse import urljoin, urlparse
from uuid import uuid4

import pytest
import requests

from pulpcore.pytest_plugin import (
    KEY_V6_MLDSA65_ED25519_PRIVATE,
    KEY_V6_MLDSA65_ED25519_PUBLIC,
    import_signing_key,
)
from pulpcore.tests.functional.utils import BindingsNamespace

from pulp_container.tests.functional.constants import PULP_HELLO_WORLD_REPO, REGISTRY_V2_FEED_URL
from pulp_container.tests.functional.utils import (
    AuthenticationHeaderQueries,
    BearerTokenAuth,
)

# A GPG-generated fixture key. Unlike the Sequoia-generated ML-DSA key (which signs with a
# dedicated subkey), this key signs with its primary key. Whether a certificate signs with its
# primary key or a subkey is a matter of key configuration, not tooling -- pulp_container must
# record the actual signing (sub)key in both cases, which the parameterization below verifies.
_GPG_FIXTURE_KEY_PRIVATE = (
    "https://raw.githubusercontent.com/pulp/pulp-fixtures/master/common/"
    "GPG-PRIVATE-KEY-fixture-signing"
)
_GPG_FIXTURE_KEY_PUBLIC = (
    "https://raw.githubusercontent.com/pulp/pulp-fixtures/master/common/GPG-KEY-fixture-signing"
)


@pytest.fixture(scope="session", params=["primary", "subkey"])
def signing_key_home(request, tmp_path_factory):
    """Import a signing key into a Sequoia home, exercising primary- and subkey-signing.

    Yields a namespace with the Sequoia `home`, the certificate `fingerprint` (primary), the
    actual `signing_fingerprint`/`signing_keyid` used when signing, and the ascii-armored
    `public_key`.
    """
    keys = {
        # GPG-generated key -> signs with its primary key.
        "primary": (_GPG_FIXTURE_KEY_PRIVATE, _GPG_FIXTURE_KEY_PUBLIC),
        # Sequoia ML-DSA (post-quantum) key -> signs with a dedicated subkey.
        "subkey": (KEY_V6_MLDSA65_ED25519_PRIVATE, KEY_V6_MLDSA65_ED25519_PUBLIC),
    }
    private_url, public_url = keys[request.param]

    home = tmp_path_factory.mktemp(f"sq_home_{request.param}")
    try:
        _sq, fingerprint, _keyid = import_signing_key(private_url, home, backend="sq")
    except TypeError:
        pytest.skip("This pulpcore release does not support the Sequoia (sq) signing backend")

    public_key = requests.get(public_url).content.decode("utf-8")
    signing_fingerprint, signing_keyid = sq_signing_identity(home, fingerprint, public_key)

    return SimpleNamespace(
        home=home,
        fingerprint=fingerprint,
        signing_fingerprint=signing_fingerprint,
        signing_keyid=signing_keyid,
        public_key=public_key,
    )


def _keyid_from_fingerprint(fingerprint):
    """Derive the key ID from an OpenPGP fingerprint, matching pulp_container's logic.

    For v4 fingerprints (40 hex chars) the key ID is the last 16 chars; for v6 (64 hex
    chars) it is the first 16 chars.
    """
    if len(fingerprint) == 40:
        return fingerprint[-16:]
    elif len(fingerprint) == 64:
        return fingerprint[:16]
    raise ValueError(f"Unexpected fingerprint length: {len(fingerprint)}")


def _verified_signing_key(public_key, raw_signature):
    """Verify an inline-signed OpenPGP message and return (signing_key_fpr, payload_bytes).

    Works for both classic (RSA/ed25519) and post-quantum (ML-DSA) keys. Uses pysequoia
    directly rather than pulpcore's gpg_verify because the latter pulls in Django models,
    which aren't configured in the functional-test client process.
    """
    from pysequoia import Cert, verify

    certs = Cert.split_bytes(public_key.encode("utf-8"))
    result = verify(bytes=raw_signature, store=lambda key_ids: certs)
    valid_sig = result.valid_sigs[0]
    return valid_sig.signing_key.upper(), bytes(result.bytes)


def verify_inline_signature(public_key, raw_signature):
    """Verify a signature blob and return (fingerprint, key_id, payload_dict)."""
    fingerprint, payload_bytes = _verified_signing_key(public_key, raw_signature)
    return fingerprint, _keyid_from_fingerprint(fingerprint), json.loads(payload_bytes)


def sq_signing_identity(sq_home, signer, public_key):
    """Return the (fingerprint, key_id) actually used when signing with `signer`.

    A certificate may sign with a dedicated subkey rather than its primary key, so the
    fingerprint recorded on produced signatures can differ from the certificate's primary
    fingerprint. This signs throwaway data to discover the real signing (sub)key.
    """
    completed = subprocess.run(
        ("sq", "--home", str(sq_home), "sign", "--signer", signer, "--message", "--binary"),
        input=b"probe",
        capture_output=True,
    )
    completed.check_returncode()
    fingerprint, _payload = _verified_signing_key(public_key, completed.stdout)
    return fingerprint, _keyid_from_fingerprint(fingerprint)


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


@pytest.fixture
def container_push_repository_factory(container_bindings):
    """Create a ContainerPushRepository directly in the database.

    Push repositories have no create API; this fixture exists to test legacy
    repositories created before pushes defaulted to ContainerRepository.
    """

    def _container_push_repository_factory(**body):
        name = body.get("name", str(uuid4()))
        pulp_domain = body.get("pulp_domain", "default")
        script = (
            "from pulp_container.app.models import ContainerPushRepository; "
            "from pulpcore.plugin.models import Domain; "
            f"domain = Domain.objects.get(name='{pulp_domain}'); "
            f"repo, _ = ContainerPushRepository.objects.get_or_create("
            f"name='{name}', pulp_domain=domain); "
        )
        subprocess.check_output(("pulpcore-manager", "shell", "-c", script))
        kwargs = {"name": name}
        if "pulp_domain" in body:
            kwargs["pulp_domain"] = pulp_domain
        # Orphan legacy push repos have no distribution until the first registry push.
        listed = container_bindings.RepositoriesContainerPushApi.list(**kwargs)
        if listed.results:
            return listed.results[0]
        return None

    return _container_push_repository_factory


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

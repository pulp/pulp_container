from types import SimpleNamespace

import pytest
from django.test import override_settings

from pulp_container.app.redirects import FileStorageRedirects, S3StorageRedirects
from pulp_container.app.registry_api import Blobs


@pytest.mark.parametrize(
    "global_redirect,domain_redirect,expected_class",
    [
        (True, False, FileStorageRedirects),
        (False, True, S3StorageRedirects),
    ],
)
def test_blob_redirect_dispatch_uses_domain_policy(
    monkeypatch, global_redirect, domain_redirect, expected_class
):
    """The Domain policy wins when it differs from the installation setting."""
    domain = SimpleNamespace(
        storage_class="storages.backends.s3boto3.S3Boto3Storage",
        redirect_to_object_storage=domain_redirect,
    )
    monkeypatch.setattr("pulp_container.app.registry_api.get_domain", lambda: domain)

    with override_settings(REDIRECT_TO_OBJECT_STORAGE=global_redirect):
        assert Blobs().redirects_class is expected_class

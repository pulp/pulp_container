import asyncio
from types import SimpleNamespace
from unittest import mock

import pytest
from django.core.exceptions import ObjectDoesNotExist

from pulp_container.app.redirects import StorageRedirects
from pulp_container.app.registry import Registry
from pulp_container.constants import BLOB_CONTENT_TYPE


def test_registry_dispatch_rejects_missing_local_file():
    """A missing file must not silently fall back to remote serving."""
    with (
        mock.patch("pulp_container.app.registry.get_domain"),
        mock.patch("pulp_container.app.registry.get_local_storage_path", return_value="/missing"),
        mock.patch("pulp_container.app.registry.os.path.exists", return_value=False),
    ):
        with pytest.raises(Exception, match="Expected path '/missing' is not found"):
            asyncio.run(
                Registry._dispatch(
                    SimpleNamespace(file=object()),
                    {"Content-Type": BLOB_CONTENT_TYPE, "Docker-Content-Digest": "sha256:abc"},
                )
            )


def test_blob_without_artifact_uses_content_app():
    """On-demand blobs without artifacts continue through the content app."""
    request = SimpleNamespace(method="GET", pulp_domain=SimpleNamespace(name="default"))
    redirects = StorageRedirects(mock.Mock(), "example", request)
    blob = SimpleNamespace(digest="sha256:abc", _artifacts=mock.Mock())
    blob._artifacts.get.side_effect = ObjectDoesNotExist
    with (
        mock.patch("pulp_container.app.redirects.get_direct_storage_url") as direct,
        mock.patch.object(redirects, "redirect_to_content_app", return_value="content") as fallback,
    ):
        assert redirects.issue_blob_redirect(blob) == "content"
    direct.assert_not_called()
    fallback.assert_called_once_with("blobs", "sha256:abc")

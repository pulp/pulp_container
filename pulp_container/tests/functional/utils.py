"""Utilities for tests for the container plugin."""

import pytest
import requests

from django.conf import settings
from requests.auth import AuthBase

from pulp_container.tests.functional.constants import (
    PULP_HELLO_WORLD_REPO,
    REGISTRY_V2_FEED_URL,
)


def get_blobsums_from_remote_registry(upstream_name=PULP_HELLO_WORLD_REPO):
    """Get remote blobsum list from a remote registry."""
    token_server_response = requests.get(
        f"{REGISTRY_V2_FEED_URL}/token?service=ghcr.io&scope=repository:{upstream_name}:pull"
    )
    token_server_response.raise_for_status()
    token = token_server_response.json()["token"]

    s = requests.Session()
    s.headers.update({"Authorization": "Bearer " + token})

    # the tag 'latest' references a manifest list
    manifest_url = f"{REGISTRY_V2_FEED_URL}/v2/{upstream_name}/manifests/latest"
    response = s.get(manifest_url)
    response.raise_for_status()

    checksums = []
    for manifest in response.json()["manifests"]:
        manifest_url = f"{REGISTRY_V2_FEED_URL}/v2/{upstream_name}/manifests/{manifest['digest']}"
        response = s.get(manifest_url)
        response.raise_for_status()

        for layer in response.json()["layers"]:
            checksums.append(layer["digest"])

    return checksums


class BearerTokenAuth(AuthBase):
    """A subclass for building a JWT Authorization header out of a provided token."""

    def __init__(self, token):
        """Store a Bearer token that is going to be used in the request object."""
        self.token = token

    def __call__(self, r):
        """Attaches a Bearer token authentication to the given request object."""
        r.headers["Authorization"] = "Bearer {}".format(self.token)
        return r


class AuthenticationHeaderQueries:
    """A data class to store header queries located in the Www-Authenticate header."""

    def __init__(self, authenticate_header):
        """
        Extract service and realm from the header.

        The scope is not provided by the token server because we are accessing the endpoint from
        the root.
        """
        self.scopes = []

        if not authenticate_header.lower().startswith("bearer "):
            raise Exception(f"Authentication header has wrong format.\n{authenticate_header}")
        for item in authenticate_header[7:].split(","):
            key, value = item.split("=")
            if key == "scope":
                self.scopes.append(value.strip('"'))
            else:
                setattr(self, key, value.strip('"'))


def get_auth_for_url(registry_endpoint_url, auth=None):
    """Return authentication details based on the the status of token authentication."""
    if settings.TOKEN_AUTH_DISABLED:
        auth = ()
    else:
        with pytest.raises(requests.HTTPError):
            response = requests.get(registry_endpoint_url)
            response.raise_for_status()
        assert response.status_code == 401

        authenticate_header = response.headers["WWW-Authenticate"]
        queries = AuthenticationHeaderQueries(authenticate_header)
        content_response = requests.get(
            queries.realm, params={"service": queries.service, "scope": queries.scopes}, auth=auth
        )
        content_response.raise_for_status()
        token = content_response.json()["token"]
        auth = BearerTokenAuth(token)

    return auth

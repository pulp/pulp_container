"""Tests that container remotes have RBAC."""

from random import choice
import pytest

from django.conf import settings

from pulp_smash import utils
from pulp_smash.pulp3.bindings import monitor_task
from pulp_smash.pulp3.constants import ON_DEMAND_DOWNLOAD_POLICIES

from pulp_container.tests.functional.utils import gen_container_remote

from pulpcore.client.pulp_container.exceptions import ApiException


@pytest.mark.parallel
def test_rbac_remotes(gen_user, container_remote_api):
    """RBAC remotes."""
    if settings.TOKEN_AUTH_DISABLED:
        pytest.skip("RBAC cannot be tested when token authentication is disabled")

    # Setup
    user1 = gen_user(model_roles=["container.containerremote_creator"])
    user2 = gen_user(model_roles=["container.containerremote_viewer"])
    user3 = gen_user()
    remote = None

    """Create a remote."""
    body = _gen_verbose_remote()
    with user2, pytest.raises(ApiException):
        container_remote_api.create(body)
    with user3, pytest.raises(ApiException):
        container_remote_api.create(body)
    with user1:
        remote = container_remote_api.create(body)

    """Read a remote by its href."""
    with user1:
        container_remote_api.read(remote.pulp_href)
    with user2:
        # read with global read permission
        container_remote_api.read(remote.pulp_href)
    with user3, pytest.raises(ApiException):
        # read without read permission
        container_remote_api.read(remote.pulp_href)

    """Read a remote by its name."""
    with user1:
        page = container_remote_api.list(name=remote.name)
        assert len(page.results) == 1
    with user2:
        page = container_remote_api.list(name=remote.name)
        assert len(page.results) == 1
    with user3:
        page = container_remote_api.list(name=remote.name)
        assert len(page.results) == 0

    """Update a remote using HTTP PATCH."""
    body = _gen_verbose_remote()
    with user2, pytest.raises(ApiException):
        container_remote_api.partial_update(remote.pulp_href, body)
    with user3, pytest.raises(ApiException):
        container_remote_api.partial_update(remote.pulp_href, body)
    with user1:
        response = container_remote_api.partial_update(remote.pulp_href, body)
        monitor_task(response.task)
        remote = container_remote_api.read(remote.pulp_href)

    """Update a remote using HTTP PUT."""
    body = _gen_verbose_remote()
    with user2, pytest.raises(ApiException):
        container_remote_api.update(remote.pulp_href, body)
    with user3, pytest.raises(ApiException):
        container_remote_api.update(remote.pulp_href, body)
    with user1:
        response = container_remote_api.update(remote.pulp_href, body)
        monitor_task(response.task)
        remote = container_remote_api.read(remote.pulp_href)

    """Delete a remote."""
    with user2, pytest.raises(ApiException):
        container_remote_api.delete(remote.pulp_href)
    with user3, pytest.raises(ApiException):
        container_remote_api.delete(remote.pulp_href)
    with user1:
        response = container_remote_api.delete(remote.pulp_href)
        monitor_task(response.task)
    with user1, pytest.raises(ApiException):
        container_remote_api.read(remote.pulp_href)


def _gen_verbose_remote():
    """Return a semi-random dict for use in defining a remote.

    For most tests, it's desirable to create remotes with as few attributes
    as possible, so that the tests can specifically target and attempt to break
    specific features. This module specifically targets remotes, so it makes
    sense to provide as many attributes as possible.

    Note that 'username' and 'password' are write-only attributes.
    """
    attrs = gen_container_remote()
    attrs.update(
        {
            "password": utils.uuid4(),
            "username": utils.uuid4(),
            "policy": choice(ON_DEMAND_DOWNLOAD_POLICIES),
        }
    )
    return attrs

"""Tests that CRUD container remotes."""

from random import choice
import pytest
import uuid

from pulp_container.tests.functional.conftest import gen_container_remote


ON_DEMAND_DOWNLOAD_POLICIES = ("on_demand", "streamed")


def test_crud_remote(container_bindings, monitor_task, add_to_cleanup):
    # Create a remote.
    body = _gen_verbose_remote()
    remote = container_bindings.RemotesContainerApi.create(body)
    add_to_cleanup(container_bindings.RemotesContainerApi, remote.pulp_href)
    for key in ("username", "password"):
        del body[key]
    for key, val in body.items():
        assert getattr(remote, key) == val, key

    # Try to create a second remote with an identical name.
    body = gen_container_remote()
    body["name"] = remote.name
    with pytest.raises(container_bindings.ApiException):
        container_bindings.RemotesContainerApi.create(body)

    # Read a remote by its href.
    read_remote = container_bindings.RemotesContainerApi.read(remote.pulp_href)
    assert read_remote.pulp_href == remote.pulp_href

    # Read a remote by its name.
    page = container_bindings.RemotesContainerApi.list(name=remote.name)
    assert len(page.results) == 1
    assert page.results[0].pulp_href == remote.pulp_href

    # Update a remote using HTTP PATCH.
    body = _gen_verbose_remote()
    response = container_bindings.RemotesContainerApi.partial_update(remote.pulp_href, body)
    monitor_task(response.task)
    for key in ("username", "password"):
        del body[key]
    remote = container_bindings.RemotesContainerApi.read(remote.pulp_href)
    for key, val in body.items():
        assert getattr(remote, key) == val, key

    # Update a remote using HTTP PUT.
    body = _gen_verbose_remote()
    response = container_bindings.RemotesContainerApi.update(remote.pulp_href, body)
    monitor_task(response.task)
    for key in ("username", "password"):
        del body[key]
    remote = container_bindings.RemotesContainerApi.read(remote.pulp_href)
    for key, val in body.items():
        assert getattr(remote, key) == val, key

    # Delete a remote.
    response = container_bindings.RemotesContainerApi.delete(remote.pulp_href)
    monitor_task(response.task)
    with pytest.raises(container_bindings.ApiException):
        container_bindings.RemotesContainerApi.read(remote.pulp_href)


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
            "password": str(uuid.uuid4()),
            "username": str(uuid.uuid4()),
            "policy": choice(ON_DEMAND_DOWNLOAD_POLICIES),
        }
    )
    return attrs

# coding=utf-8
"""Tests that container remotes have RBAC."""
from random import choice
import unittest

from pulp_smash import utils
from pulp_smash.pulp3.bindings import monitor_task
from pulp_smash.pulp3.constants import ON_DEMAND_DOWNLOAD_POLICIES

from pulp_container.tests.functional.utils import (
    del_user,
    gen_container_remote,
    gen_user,
    skip_if,
)

from pulpcore.client.pulp_container.exceptions import ApiException


class RBACRemotesTestCase(unittest.TestCase):
    """RBAC remotes."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables and prepare api users."""
        cls.user1 = gen_user(["container.add_containerremote"])
        cls.user2 = gen_user(["container.view_containerremote"])
        cls.user3 = gen_user([])
        cls.remote = None

    @classmethod
    def tearDownClass(cls):
        """Delete api users."""
        del_user(cls.user1)
        del_user(cls.user2)
        del_user(cls.user3)

    def test_01_create_remote(self):
        """Create a remote."""
        body = _gen_verbose_remote()
        with self.assertRaises(ApiException):
            self.user2["remote_api"].create(body)
        with self.assertRaises(ApiException):
            self.user3["remote_api"].create(body)
        type(self).remote = self.user1["remote_api"].create(body)

    @skip_if(bool, "remote", False)
    def test_02_read_remote(self):
        """Read a remote by its href."""
        self.user1["remote_api"].read(self.remote.pulp_href)
        # read with global read permission
        self.user2["remote_api"].read(self.remote.pulp_href)
        # read without read permission
        with self.assertRaises(ApiException):
            self.user3["remote_api"].read(self.remote.pulp_href)

    @skip_if(bool, "remote", False)
    def test_02_read_remotes(self):
        """Read a remote by its name."""
        page = self.user1["remote_api"].list(name=self.remote.name)
        self.assertEqual(len(page.results), 1)
        page = self.user2["remote_api"].list(name=self.remote.name)
        self.assertEqual(len(page.results), 1)
        page = self.user3["remote_api"].list(name=self.remote.name)
        self.assertEqual(len(page.results), 0)

    @skip_if(bool, "remote", False)
    def test_03_partially_update(self):
        """Update a remote using HTTP PATCH."""
        body = _gen_verbose_remote()
        with self.assertRaises(ApiException):
            self.user2["remote_api"].partial_update(self.remote.pulp_href, body)
        with self.assertRaises(ApiException):
            self.user3["remote_api"].partial_update(self.remote.pulp_href, body)
        response = self.user1["remote_api"].partial_update(self.remote.pulp_href, body)
        monitor_task(response.task)
        type(self).remote = self.user1["remote_api"].read(self.remote.pulp_href)

    @skip_if(bool, "remote", False)
    def test_04_fully_update(self):
        """Update a remote using HTTP PUT."""
        body = _gen_verbose_remote()
        with self.assertRaises(ApiException):
            self.user2["remote_api"].update(self.remote.pulp_href, body)
        with self.assertRaises(ApiException):
            self.user3["remote_api"].update(self.remote.pulp_href, body)
        response = self.user1["remote_api"].update(self.remote.pulp_href, body)
        monitor_task(response.task)
        type(self).remote = self.user1["remote_api"].read(self.remote.pulp_href)

    @skip_if(bool, "remote", False)
    def test_05_delete(self):
        """Delete a remote."""
        with self.assertRaises(ApiException):
            self.user2["remote_api"].delete(self.remote.pulp_href)
        with self.assertRaises(ApiException):
            self.user3["remote_api"].delete(self.remote.pulp_href)
        response = self.user1["remote_api"].delete(self.remote.pulp_href)
        monitor_task(response.task)
        with self.assertRaises(ApiException):
            self.user1["remote_api"].read(self.remote.pulp_href)


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

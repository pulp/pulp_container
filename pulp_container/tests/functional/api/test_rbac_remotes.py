# coding=utf-8
"""Tests that container remotes have RBAC."""
from random import choice
import unittest

from pulp_smash import cli, config, utils
from pulp_smash.pulp3.bindings import monitor_task
from pulp_smash.pulp3.constants import ON_DEMAND_DOWNLOAD_POLICIES

from pulp_container.tests.functional.utils import (
    gen_container_remote,
    skip_if,
)

from pulpcore.client.pulp_container import (
    ApiClient as ContainerApiClient,
    RemotesContainerApi,
)
from pulpcore.client.pulp_container.exceptions import ApiException


CREATE_USER_CMD = [
    "from django.contrib.auth import get_user_model",
    "from django.contrib.auth.models import Permission",
    "",
    "user = get_user_model().objects.create(username='{username}')",
    "user.set_password('{password}')",
    "user.save()",
    "for permission in {permissions!r}:",
    "    if '.' in permission:",
    "        app_label, codename = permission.split('.', maxsplit=1)",
    "        perm = Permission.objects.get(codename=codename, content_type__app_label=app_label)",
    "    else:",
    "        perm = Permission.objects.get(codename=permission)",
    "    user.user_permissions.add(perm)",
]


DELETE_USER_CMD = [
    "from django.contrib.auth import get_user_model",
    "get_user_model().objects.get(username='{username}').delete()",
]


class RBACRemotesTestCase(unittest.TestCase):
    """RBAC remotes."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables and prepare api users."""
        cls.cfg = config.get_config()
        cls.cli_client = cli.Client(cls.cfg)
        cls.user1 = {
            "username": utils.uuid4(),
            "password": utils.uuid4(),
            "permissions": ["container.add_containerremote"],
        }
        utils.execute_pulpcore_python(
            cls.cli_client,
            "\n".join(CREATE_USER_CMD).format(**cls.user1),
        )
        cls.api_config = cls.cfg.get_bindings_config()
        cls.api_config.username = cls.user1["username"]
        cls.api_config.password = cls.user1["password"]
        cls.api_client = ContainerApiClient(cls.api_config)
        cls.remote_api = RemotesContainerApi(cls.api_client)
        cls.remote = None

    @classmethod
    def tearDownClass(cls):
        """Delete api users."""
        utils.execute_pulpcore_python(
            cls.cli_client,
            "\n".join(DELETE_USER_CMD).format(**cls.user1),
        )

    def test_01_create_remote(self):
        """Create a remote."""
        body = _gen_verbose_remote()
        type(self).remote = self.remote_api.create(body)
        for key in ("username", "password"):
            del body[key]
        for key, val in body.items():
            with self.subTest(key=key):
                self.assertEqual(self.remote.to_dict()[key], val, key)

    @skip_if(bool, "remote", False)
    def test_02_create_same_name(self):
        """Try to create a second remote with an identical name.

        See: `Pulp Smash #1055
        <https://github.com/pulp/pulp-smash/issues/1055>`_.
        """
        body = gen_container_remote()
        body["name"] = self.remote.name
        with self.assertRaises(ApiException):
            self.remote_api.create(body)

    @skip_if(bool, "remote", False)
    def test_02_read_remote(self):
        """Read a remote by its href."""
        remote = self.remote_api.read(self.remote.pulp_href)
        for key, val in self.remote.to_dict().items():
            with self.subTest(key=key):
                self.assertEqual(remote.to_dict()[key], val, key)

    @skip_if(bool, "remote", False)
    def test_02_read_remotes(self):
        """Read a remote by its name."""
        page = self.remote_api.list(name=self.remote.name)
        self.assertEqual(len(page.results), 1)
        for key, val in self.remote.to_dict().items():
            with self.subTest(key=key):
                self.assertEqual(page.results[0].to_dict()[key], val, key)

    @skip_if(bool, "remote", False)
    def test_03_partially_update(self):
        """Update a remote using HTTP PATCH."""
        body = _gen_verbose_remote()
        response = self.remote_api.partial_update(self.remote.pulp_href, body)
        monitor_task(response.task)
        for key in ("username", "password"):
            del body[key]
        type(self).remote = self.remote_api.read(self.remote.pulp_href)
        for key, val in body.items():
            with self.subTest(key=key):
                self.assertEqual(self.remote.to_dict()[key], val, key)

    @skip_if(bool, "remote", False)
    def test_04_fully_update(self):
        """Update a remote using HTTP PUT."""
        body = _gen_verbose_remote()
        response = self.remote_api.update(self.remote.pulp_href, body)
        monitor_task(response.task)
        for key in ("username", "password"):
            del body[key]
        type(self).remote = self.remote_api.read(self.remote.pulp_href)
        for key, val in body.items():
            with self.subTest(key=key):
                self.assertEqual(self.remote.to_dict()[key], val, key)

    @skip_if(bool, "remote", False)
    def test_05_delete(self):
        """Delete a remote."""
        response = self.remote_api.delete(self.remote.pulp_href)
        monitor_task(response.task)
        with self.assertRaises(ApiException):
            self.remote_api.read(self.remote.pulp_href)


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

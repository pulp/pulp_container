# coding=utf-8
"""Tests that container repositories have RBAC."""
import unittest

from pulp_smash import utils
from pulp_smash.pulp3.bindings import monitor_task

from pulp_container.tests.functional.utils import (
    del_user,
    gen_user,
    skip_if,
)

from pulpcore.client.pulp_container.exceptions import ApiException


class RBACRepositoriesTestCase(unittest.TestCase):
    """RBAC repositories."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables and prepare api users."""
        cls.user1 = gen_user(["container.add_containerrepository"])
        cls.user2 = gen_user(["container.view_containerrepository"])
        cls.user3 = gen_user([])
        cls.repository = None

    @classmethod
    def tearDownClass(cls):
        """Delete api users."""
        del_user(cls.user1)
        del_user(cls.user2)
        del_user(cls.user3)

    def test_01_create_repository(self):
        """Create a repository."""
        body = {"name": utils.uuid4()}
        with self.assertRaises(ApiException):
            self.user2["repository_api"].create(body)
        with self.assertRaises(ApiException):
            self.user3["repository_api"].create(body)
        type(self).repository = self.user1["repository_api"].create(body)

    @skip_if(bool, "repository", False)
    def test_02_read_repository(self):
        """Read a repository by its href."""
        self.user1["repository_api"].read(self.repository.pulp_href)
        # read with global read permission
        self.user2["repository_api"].read(self.repository.pulp_href)
        # read without read permission
        with self.assertRaises(ApiException):
            self.user3["repository_api"].read(self.repository.pulp_href)

    @skip_if(bool, "repository", False)
    def test_02_read_repositories(self):
        """Read a repository by its name."""
        page = self.user1["repository_api"].list(name=self.repository.name)
        self.assertEqual(len(page.results), 1)
        page = self.user2["repository_api"].list(name=self.repository.name)
        self.assertEqual(len(page.results), 1)
        page = self.user3["repository_api"].list(name=self.repository.name)
        self.assertEqual(len(page.results), 0)

    @skip_if(bool, "repository", False)
    def test_03_partially_update(self):
        """Update a repository using HTTP PATCH."""
        body = {"name": utils.uuid4()}
        with self.assertRaises(ApiException):
            self.user2["repository_api"].partial_update(self.repository.pulp_href, body)
        with self.assertRaises(ApiException):
            self.user3["repository_api"].partial_update(self.repository.pulp_href, body)
        response = self.user1["repository_api"].partial_update(self.repository.pulp_href, body)
        monitor_task(response.task)
        type(self).repository = self.user1["repository_api"].read(self.repository.pulp_href)

    @skip_if(bool, "repository", False)
    def test_04_fully_update(self):
        """Update a repository using HTTP PUT."""
        body = {"name": utils.uuid4()}
        with self.assertRaises(ApiException):
            self.user2["repository_api"].update(self.repository.pulp_href, body)
        with self.assertRaises(ApiException):
            self.user3["repository_api"].update(self.repository.pulp_href, body)
        response = self.user1["repository_api"].update(self.repository.pulp_href, body)
        monitor_task(response.task)
        type(self).repository = self.user1["repository_api"].read(self.repository.pulp_href)

    @skip_if(bool, "repository", False)
    def test_05_delete(self):
        """Delete a repository."""
        with self.assertRaises(ApiException):
            self.user2["repository_api"].delete(self.repository.pulp_href)
        with self.assertRaises(ApiException):
            self.user3["repository_api"].delete(self.repository.pulp_href)
        response = self.user1["repository_api"].delete(self.repository.pulp_href)
        monitor_task(response.task)
        with self.assertRaises(ApiException):
            self.user1["repository_api"].read(self.repository.pulp_href)

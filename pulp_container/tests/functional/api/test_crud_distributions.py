# coding=utf-8
"""Tests that CRUD distributions."""
import json
import unittest

from itertools import permutations

from pulp_smash import utils
from pulp_smash.pulp3.bindings import monitor_task
from pulp_smash.pulp3.utils import gen_distribution

from pulp_container.tests.functional.utils import (
    skip_if,
    gen_container_client,
)

from pulpcore.client.pulp_container import (
    ApiException,
    ContainerContainerDistribution,
    DistributionsContainerApi,
)


class CRUDContainerDistributionsTestCase(unittest.TestCase):
    """CRUD distributions."""

    @classmethod
    def setUpClass(cls):
        """Create class wide-variables."""
        client_api = gen_container_client()
        cls.distribution_api = DistributionsContainerApi(client_api)
        cls.distribution = {}

    def test_01_create_distribution(self):
        """Create a distribution."""
        body = gen_distribution()
        distribution_data = ContainerContainerDistribution(**body)
        distribution_response = self.distribution_api.create(distribution_data)
        created_resources = monitor_task(distribution_response.task).created_resources

        distribution_obj = self.distribution_api.read(created_resources[0])
        self.distribution.update(distribution_obj.to_dict())
        for key, val in body.items():
            with self.subTest(key=key):
                self.assertEqual(self.distribution[key], val)

    @skip_if(bool, "distribution", False)
    def test_02_create_same_name(self):
        """Try to create a second distribution with an identical name.

        See: `Pulp Smash #1055
        <https://github.com/pulp/pulp-smash/issues/1055>`_.
        """
        body = gen_distribution()
        body["name"] = self.distribution["name"]
        distribution_data = ContainerContainerDistribution(**body)
        with self.assertRaises(ApiException):
            self.distribution_api.create(distribution_data)

    @skip_if(bool, "distribution", False)
    def test_02_read_distribution(self):
        """Read a distribution by its pulp_href."""
        distribution_obj = self.distribution_api.read(self.distribution["pulp_href"])
        for key, val in self.distribution.items():
            with self.subTest(key=key):
                self.assertEqual(getattr(distribution_obj, key), val)

    @skip_if(bool, "distribution", False)
    def test_02_read_distribution_with_specific_fields(self):
        """Read a distribution by its href providing specific field list.

        Permutate field list to ensure different combinations on result.
        """
        for field_pair in permutations(("base_path", "name")):
            with self.subTest(field_pair=field_pair):
                distribution = self.distribution_api.read(
                    self.distribution["pulp_href"], fields=",".join(field_pair)
                ).to_dict()
                # a distribution object contains always all fields; due to that, it is
                # necessary to filter out only the keys which do not have the None value
                filtered_keys = filter(lambda x: bool(distribution[x]), distribution)
                self.assertEqual(sorted(field_pair), sorted(filtered_keys))

    @skip_if(bool, "distribution", False)
    def test_02_read_distribution_without_specific_fields(self):
        """Read a distribution by its href excluding specific fields."""
        for field_pair in permutations(("pulp_href", "registry_path")):
            with self.subTest(field_pair=field_pair):
                # FIXME: an API object returns an object of type 'ContainerContainerDistribution'
                #  and during its initialization, there is an explicit check for the required
                #  fields 'base_path' and 'name'; these two fields have to be present at the time
                #  of the instantiation
                distribution = self.distribution_api.read(
                    self.distribution["pulp_href"], exclude_fields=",".join(field_pair)
                ).to_dict()
                filtered_keys = list(filter(lambda x: bool(distribution[x]), distribution))
                self.assertNotIn("pulp_href", filtered_keys)
                self.assertNotIn("registry_path", filtered_keys)

    @skip_if(bool, "distribution", False)
    def test_02_read_distributions(self):
        """Read a distribution using query parameters.

        See: `Pulp #3082 <https://pulp.plan.io/issues/3082>`_
        """
        unique_params = (
            {"name": self.distribution["name"]},
            {"base_path": self.distribution["base_path"]},
        )
        for params in unique_params:
            with self.subTest(params=params):
                page = self.distribution_api.list(**params)
                self.assertEqual(len(page.results), 1)
                for key, val in self.distribution.items():
                    with self.subTest(key=key):
                        self.assertEqual(getattr(page.results[0], key), val)

    @skip_if(bool, "distribution", False)
    def test_03_partially_update(self):
        """Update a distribution using HTTP PATCH."""
        body = gen_distribution()
        distribution_data = ContainerContainerDistribution(**body)
        distribution_response = self.distribution_api.partial_update(
            self.distribution["pulp_href"], distribution_data
        )
        monitor_task(distribution_response.task)

        distribution_obj = self.distribution_api.read(self.distribution["pulp_href"])

        self.distribution.clear()
        self.distribution.update(distribution_obj.to_dict())
        for key, val in body.items():
            with self.subTest(key=key):
                self.assertEqual(self.distribution[key], val)

    @skip_if(bool, "distribution", False)
    def test_04_fully_update(self):
        """Update a distribution using HTTP PUT."""
        body = gen_distribution()
        distribution_data = ContainerContainerDistribution(**body)
        distribution_response = self.distribution_api.update(
            self.distribution["pulp_href"], distribution_data
        )
        monitor_task(distribution_response.task)

        distribution_obj = self.distribution_api.read(self.distribution["pulp_href"])

        self.distribution.clear()
        self.distribution.update(distribution_obj.to_dict())
        for key, val in body.items():
            with self.subTest(key=key):
                self.assertEqual(self.distribution[key], val)

    @skip_if(bool, "distribution", False)
    def test_05_delete(self):
        """Delete a distribution."""
        delete_response = self.distribution_api.delete(self.distribution["pulp_href"])
        monitor_task(delete_response.task)
        with self.assertRaises(ApiException):
            self.distribution_api.read(self.distribution["pulp_href"])

    def test_negative_create_distribution_with_invalid_parameter(self):
        """Attempt to create distribution passing invalid parameter.

        Assert response returns an error 400 including ["Unexpected field"].
        """
        with self.assertRaises(ApiException) as exc:
            self.distribution_api.create(gen_distribution(foo="bar"))

        assert exc.exception.status == 400
        assert json.loads(exc.exception.body)["foo"] == ["Unexpected field"]


class DistributionBasePathTestCase(unittest.TestCase):
    """Test possible values for ``base_path`` on a distribution.

    This test targets the following issues:

    * `Pulp #2987 <https://pulp.plan.io/issues/2987>`_
    * `Pulp #3412 <https://pulp.plan.io/issues/3412>`_
    * `Pulp Smash #906 <https://github.com/pulp/pulp-smash/issues/906>`_
    * `Pulp Smash #956 <https://github.com/pulp/pulp-smash/issues/956>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        client_api = gen_container_client()
        cls.distribution_api = DistributionsContainerApi(client_api)

        body = gen_distribution()
        body["base_path"] = body["base_path"].replace("-", "/")
        distribution_data = ContainerContainerDistribution(**body)
        distribution_response = cls.distribution_api.create(distribution_data)
        created_resources = monitor_task(distribution_response.task).created_resources

        cls.distribution = cls.distribution_api.read(created_resources[0])

    @classmethod
    def tearDownClass(cls):
        """Clean up resources."""
        cls.distribution_api.delete(cls.distribution.pulp_href)

    def test_spaces(self):
        """Test that spaces can not be part of ``base_path``."""
        self.try_create_distribution(base_path=utils.uuid4().replace("-", " "))
        self.try_update_distribution(base_path=utils.uuid4().replace("-", " "))

    def test_begin_slash(self):
        """Test that slash cannot be in the begin of ``base_path``."""
        self.try_create_distribution(base_path="/" + utils.uuid4())
        self.try_update_distribution(base_path="/" + utils.uuid4())

    def test_end_slash(self):
        """Test that slash cannot be in the end of ``base_path``."""
        self.try_create_distribution(base_path=utils.uuid4() + "/")
        self.try_update_distribution(base_path=utils.uuid4() + "/")

    def test_unique_base_path(self):
        """Test that ``base_path`` can not be duplicated."""
        self.try_create_distribution(base_path=self.distribution.base_path)

    def try_create_distribution(self, **kwargs):
        """Unsuccessfully create a distribution.

        Merge the given kwargs into the body of the request.
        """
        body = gen_distribution()
        body.update(kwargs)
        with self.assertRaises(ApiException):
            self.distribution_api.create(body)

    def try_update_distribution(self, **kwargs):
        """Unsuccessfully update a distribution with HTTP PATCH.

        Use the given kwargs as the body of the request.
        """
        with self.assertRaises(ApiException):
            self.distribution_api.partial_update(self.distribution.pulp_href, kwargs)

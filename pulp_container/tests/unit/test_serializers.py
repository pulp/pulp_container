from uuid import UUID, uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase

from pulpcore.plugin.models import Distribution
from pulpcore.plugin.util import set_current_user

from pulp_container.app.models import (
    ContainerPullThroughDistribution,
    ContainerPullThroughRemote,
    ContainerPushRepository,
    ContainerRepository,
)
from pulp_container.app.serializers import (
    ContainerDistributionSerializer,
    ContainerPullThroughDistributionSerializer,
    TagOperationSerializer,
)
from pulp_container.constants import PULL_THROUGH_DISTRIBUTION_LABEL

V3_API_ROOT = (
    settings.API_ROOT + "default/api/v3/" if settings.DOMAIN_ENABLED else settings.V3_API_ROOT
)


class TestContainerDistributionSerializer(TestCase):
    """Test ContainerDistributionSerializer."""

    def setUp(self):
        """Set up the ContainerDistributionSerializer tests."""
        self.mirror_repository, _ = ContainerRepository.objects.get_or_create(
            name="mirror repository",
        )
        self.mirror_repository_href = (
            f"{V3_API_ROOT}repositories/container/container/{self.mirror_repository.pk}/"
        )
        self.push_repository, _ = ContainerPushRepository.objects.get_or_create(
            name="push repository",
        )
        self.push_repository_href = (
            f"{V3_API_ROOT}repositories/container/container-push/{self.push_repository.pk}/"
        )
        self.user = get_user_model().objects.create(username="user1")
        set_current_user(self.user)

    def tearDown(self):
        """Delete the user."""
        super().tearDown()
        self.user.delete()
        set_current_user(None)

    def test_valid_mirror_data(self):
        """Test that the ContainerDistributionSerializer accepts valid data."""
        data = {
            "name": "mirror distribution",
            "base_path": "test/mirror",
            "repository": self.mirror_repository_href,
        }
        serializer = ContainerDistributionSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_valid_mirror_version_data(self):
        """Test that the ContainerDistributionSerializer accepts valid data."""
        data = {
            "name": "mirror distribution",
            "base_path": "test/mirror",
            "repository_version": self.mirror_repository_href + "versions/0/",
        }
        serializer = ContainerDistributionSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_valid_push_data(self):
        """Test that the ContainerDistributionSerializer accepts valid data."""
        data = {
            "name": "mirror distribution",
            "base_path": "test/mirror",
            "repository": self.push_repository_href,
        }
        serializer = ContainerDistributionSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_invalid_push_version_data(self):
        """Test that the ContainerDistributionSerializer does not accept invalid data."""
        data = {
            "name": "push distribution",
            "base_path": "test/push",
            "repository_version": self.push_repository_href + "versions/0/",
        }
        serializer = ContainerDistributionSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("non_field_errors", serializer.errors)
        self.assertIn("cannot be distributed", str(serializer.errors["non_field_errors"][0]))

    def test_base_path_cannot_contain_another_distribution(self):
        """Test that the base path cannot contain another distribution's base path."""
        Distribution.objects.create(name="distribution", base_path="test")
        data = {
            "name": "container distribution",
            "base_path": "test/container",
            "repository": self.mirror_repository_href,
        }

        serializer = ContainerDistributionSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertIn("base_path", serializer.errors)

    def test_base_path_cannot_be_parent_of_another_distribution(self):
        """Test that the base path cannot be the parent of another distribution's base path."""
        Distribution.objects.create(name="distribution", base_path="test/file")
        data = {
            "name": "container distribution",
            "base_path": "test",
            "repository": self.mirror_repository_href,
        }

        serializer = ContainerDistributionSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertIn("base_path", serializer.errors)


class TestTagOperationSerializer(TestCase):
    """Test TagOperationSerializer."""

    def setUp(self):
        """Create a new repository."""
        self.repository, _ = ContainerRepository.objects.get_or_create(name="tag repository")

    def test_valid_tag(self):
        """Test the serializer while passing a valid tag."""
        serializer = TagOperationSerializer(
            data={"tag": "valid-tag"}, context={"repository": self.repository}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_invalid_tag(self):
        """Test the serializer while passing an invalid tag."""
        serializer = TagOperationSerializer(
            data={"tag": ".invalid-tag"}, context={"repository": self.repository}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("tag", serializer.errors)
        self.assertIn("tag is not valid", str(serializer.errors["tag"][0]))


class TestContainerPullThroughDistributionSerializer(TestCase):
    """Test the temporary pull-through base-path handling."""

    def setUp(self):
        self.user = get_user_model().objects.create(username="pull-through-user")
        set_current_user(self.user)
        self.remote = ContainerPullThroughRemote.objects.create(
            name="pull-through remote",
            url="https://registry.example.com",
            policy="on_demand",
        )
        self.remote_href = f"{V3_API_ROOT}remotes/container/pull-through/{self.remote.pk}/"

    def tearDown(self):
        super().tearDown()
        self.user.delete()
        set_current_user(None)

    def test_create_moves_base_path_and_marks_distribution(self):
        data = {
            "name": "pull-through distribution",
            "base_path": "registry-cache",
            "remote": self.remote_href,
        }

        serializer = ContainerPullThroughDistributionSerializer(data=data)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        UUID(serializer.validated_data["base_path"])
        self.assertEqual(
            serializer.validated_data["pulp_labels"][PULL_THROUGH_DISTRIBUTION_LABEL],
            "registry-cache",
        )
        self.assertEqual(serializer.validated_data["namespace"].name, "registry-cache")

    def test_create_allows_different_name_and_base_path(self):
        data = {
            "name": "pull-through distribution",
            "base_path": "registry-cache/team",
            "remote": self.remote_href,
        }

        serializer = ContainerPullThroughDistributionSerializer(data=data)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["pulp_labels"][PULL_THROUGH_DISTRIBUTION_LABEL],
            "registry-cache/team",
        )
        self.assertEqual(serializer.validated_data["namespace"].name, "registry-cache")

    def test_create_rejects_invalid_registry_path(self):
        data = {
            "name": "pull-through distribution",
            "base_path": "Invalid Path",
            "remote": self.remote_href,
        }

        serializer = ContainerPullThroughDistributionSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertIn("base_path", serializer.errors)

    def test_create_fails_for_existing_base_path(self):
        Distribution.objects.create(name="ordinary distribution", base_path="registry-cache")
        data = {
            "name": "registry-cache",
            "base_path": "registry-cache",
            "remote": self.remote_href,
        }

        serializer = ContainerPullThroughDistributionSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertIn("base_path", serializer.errors)

    def test_update_allows_non_base_path_change_for_unmarked_distribution(self):
        distribution = ContainerPullThroughDistribution.objects.create(
            name="registry-cache",
            base_path="registry-cache",
            remote=self.remote,
        )
        serializer = ContainerPullThroughDistributionSerializer(
            distribution, data={"description": "updated"}, partial=True
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertNotIn("base_path", serializer.validated_data)
        self.assertNotIn("pulp_labels", serializer.validated_data)

    def test_update_rejects_unmarked_base_path_change_with_repair_instruction(self):
        distribution = ContainerPullThroughDistribution.objects.create(
            name="registry-cache",
            base_path="different-path",
            remote=self.remote,
        )
        serializer = ContainerPullThroughDistributionSerializer(
            distribution, data={"base_path": str(uuid4())}, partial=True
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("base_path", serializer.errors)
        self.assertIn(
            "container-repair-pull-through-distributions", str(serializer.errors["base_path"])
        )

    def test_update_allows_unchanged_base_path(self):
        distribution = ContainerPullThroughDistribution.objects.create(
            name="registry-cache",
            base_path="registry-cache",
            remote=self.remote,
        )
        serializer = ContainerPullThroughDistributionSerializer(
            distribution, data={"base_path": distribution.base_path}, partial=True
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_update_rejects_repaired_base_path_change(self):
        distribution = ContainerPullThroughDistribution.objects.create(
            name="registry-cache",
            base_path=str(uuid4()),
            remote=self.remote,
            pulp_labels={PULL_THROUGH_DISTRIBUTION_LABEL: "registry-cache"},
        )
        serializer = ContainerPullThroughDistributionSerializer(
            distribution, data={"base_path": str(uuid4())}, partial=True
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("base_path", serializer.errors)
        self.assertIn("cannot be updated", str(serializer.errors["base_path"]))

from django.contrib.auth import get_user_model
from django.test import TestCase

from django_currentuser.middleware import _set_current_user

from pulp_container.app.serializers import ContainerDistributionSerializer, TagOperationSerializer
from pulp_container.app.models import ContainerPushRepository, ContainerRepository


class TestContainerDistributionSerializer(TestCase):
    """Test ContainerDistributionSerializer."""

    def setUp(self):
        """Set up the ContainerDistributionSerializer tests."""
        self.mirror_repository, _ = ContainerRepository.objects.get_or_create(
            name="mirror repository",
        )
        self.mirror_repository_href = "/pulp/api/v3/repositories/container/container/{}/".format(
            self.mirror_repository.pk
        )
        self.push_repository, _ = ContainerPushRepository.objects.get_or_create(
            name="push repository",
        )
        self.push_repository_href = "/pulp/api/v3/repositories/container/container-push/{}/".format(
            self.push_repository.pk
        )
        self.user = get_user_model().objects.create(username="user1", is_staff=False)
        _set_current_user(self.user)

    def tearDown(self):
        """Delete the user."""
        super().tearDown()
        self.user.delete()
        _set_current_user(None)

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


class TestTagOperationSerializer(TestCase):
    """Test TagOperationSerializer."""

    def setUp(self):
        """Create a new repository."""
        self.repository, _ = ContainerRepository.objects.get_or_create(name="tag repository")

    def test_valid_tag(self):
        """Test the serializer while passing a valid tag."""
        serializer = TagOperationSerializer(
            data={"tag": "valid-tag", "repository": self.repository}
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_invalid_tag(self):
        """Test the serializer while passing an invalid tag."""
        serializer = TagOperationSerializer(
            data={"tag": ".invalid-tag", "repository": self.repository}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("tag", serializer.errors)
        self.assertIn("tag is not valid", str(serializer.errors["tag"][0]))

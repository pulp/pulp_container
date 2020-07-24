from django.test import TestCase

from pulp_container.app.serializers import ContainerDistributionSerializer
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

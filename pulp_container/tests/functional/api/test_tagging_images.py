# coding=utf-8
"""Tests for tagging and untagging images."""
import unittest

from pulp_smash import api, config
from pulp_smash.pulp3.utils import gen_repo, sync

from pulp_container.tests.functional.utils import set_up_module as setUpModule  # noqa:F401
from pulp_container.tests.functional.utils import gen_container_remote

from pulp_container.tests.functional.constants import (
    CONTAINER_TAG_PATH,
    CONTAINER_REMOTE_PATH,
    CONTAINER_REPO_PATH,
    DOCKERHUB_PULP_FIXTURE_1,
)
from requests import HTTPError


class TaggingTestCase(unittest.TestCase):
    """Test case for tagging and untagging images."""

    @classmethod
    def setUpClass(cls):
        """Create class wide-variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)

        cls.repository = cls.client.post(CONTAINER_REPO_PATH, gen_repo())
        remote_data = gen_container_remote(upstream_name=DOCKERHUB_PULP_FIXTURE_1)
        cls.remote = cls.client.post(CONTAINER_REMOTE_PATH, remote_data)
        sync(cls.cfg, cls.remote, cls.repository)

    @classmethod
    def tearDownClass(cls):
        """Clean generated resources."""
        cls.client.delete(cls.repository['pulp_href'])
        cls.client.delete(cls.remote['pulp_href'])

    def test_01_tag_first_image(self):
        """
        Create a new test for manifest.

        This test checks if the tag was created in a new repository version.
        """
        manifest_a = self.get_manifest_by_tag('manifest_a')
        self.tag_image(manifest_a, 'new_tag')

        new_repository_version_href = '{repository_href}versions/{new_version}/'.format(
            repository_href=self.repository['pulp_href'],
            new_version='2'
        )

        added_tags_href = '{unit_path}?{filters}'.format(
            unit_path=CONTAINER_TAG_PATH,
            filters=f'repository_version_added={new_repository_version_href}'
        )
        created_tag = self.client.get(added_tags_href)['results'][0]
        self.assertEqual(created_tag['name'], 'new_tag', created_tag['name'])

        repository_version = self.client.get(new_repository_version_href)

        added_content = repository_version['content_summary']['added']
        added_tags = added_content['container.tag']['count']
        self.assertEqual(added_tags, 1, added_content)

        removed_content = repository_version['content_summary']['removed']
        self.assertEqual(removed_content, {}, removed_content)

    def test_02_tag_first_image_with_same_tag(self):
        """
        Tag the same manifest with the same name.

        This test checks if a new repository version was created with no content added.
        """
        latest_version_before = self.client.get(
            self.repository['pulp_href']
        )['latest_version_href']

        manifest_a = self.get_manifest_by_tag('manifest_a')
        self.tag_image(manifest_a, 'new_tag')

        latest_version_after = self.client.get(
            self.repository['pulp_href']
        )['latest_version_href']

        self.assertEquals(latest_version_before, latest_version_after)

    def test_03_tag_second_image_with_same_tag(self):
        """
        Tag a different manifest with the same name.

        This test checks if a new repository version was created with a new content added
        and the old removed.
        """
        manifest_a = self.get_manifest_by_tag('manifest_a')
        manifest_b = self.get_manifest_by_tag('manifest_b')
        self.tag_image(manifest_b, 'new_tag')

        new_repository_version_href = '{repository_href}versions/{new_version}/'.format(
            repository_href=self.repository['pulp_href'],
            new_version='3'
        )

        added_tags_href = '{unit_path}?{filters}'.format(
            unit_path=CONTAINER_TAG_PATH,
            filters=f'repository_version_added={new_repository_version_href}'
        )
        created_tag = self.client.get(added_tags_href)['results'][0]
        self.assertEqual(created_tag['name'], 'new_tag', created_tag['name'])

        created_tag_manifest = self.client.get(created_tag['tagged_manifest'])
        self.assertEqual(created_tag_manifest, manifest_b, created_tag_manifest)

        removed_tags_href = '{unit_path}?{filters}'.format(
            unit_path=CONTAINER_TAG_PATH,
            filters=f'repository_version_removed={new_repository_version_href}'
        )
        removed_tag = self.client.get(removed_tags_href)['results'][0]
        self.assertEqual(removed_tag['name'], 'new_tag', removed_tag['name'])

        removed_tag_manifest = self.client.get(removed_tag['tagged_manifest'])
        self.assertEqual(removed_tag_manifest, manifest_a, removed_tag_manifest)

        repository_version = self.client.get(new_repository_version_href)

        added_content = repository_version['content_summary']['added']
        added_tags = added_content['container.tag']['count']
        self.assertEqual(added_tags, 1, added_content)

        removed_content = repository_version['content_summary']['removed']
        removed_tags = removed_content['container.tag']['count']
        self.assertEqual(removed_tags, 1, removed_content)

    def test_04_untag_second_image(self):
        """Untag the manifest and check if the tag was added in a new repository version."""
        self.untag_image('new_tag')

        new_repository_version_href = '{repository_href}versions/{new_version}/'.format(
            repository_href=self.repository['pulp_href'],
            new_version='4'
        )

        removed_tags_href = '{unit_path}?{filters}'.format(
            unit_path=CONTAINER_TAG_PATH,
            filters=f'repository_version_removed={new_repository_version_href}'
        )

        repository_version = self.client.get(new_repository_version_href)

        removed_content = repository_version['content_summary']['removed']
        removed_tags = removed_content['container.tag']['href']
        self.assertEqual(removed_tags, removed_tags_href, removed_tags)

        added_content = repository_version['content_summary']['added']
        self.assertEqual(added_content, {}, added_content)

        removed_tag = self.client.get(removed_tags_href)['results'][0]
        self.assertEqual(removed_tag['name'], 'new_tag', removed_tag)

    def test_05_untag_second_image_again(self):
        """Untag the manifest that was already untagged."""
        with self.assertRaises(HTTPError):
            self.untag_image('new_tag')

    def get_manifest_by_tag(self, tag_name):
        """Fetch a manifest by the tag name."""
        latest_version = self.client.get(
            self.repository['pulp_href']
        )['latest_version_href']

        manifest_a_href = self.client.get('{unit_path}?{filters}'.format(
            unit_path=CONTAINER_TAG_PATH,
            filters=f'name={tag_name}&repository_version={latest_version}'
        ))['results'][0]['tagged_manifest']
        return self.client.get(manifest_a_href)

    def tag_image(self, manifest, tag_name):
        """Perform a tagging operation."""
        params = {
            'tag': tag_name,
            'digest': manifest['digest']
        }
        self.client.post(f'{self.repository["pulp_href"]}tag/', params)

    def untag_image(self, tag_name):
        """Perform an untagging operation."""
        params = {
            'tag': tag_name,
        }
        self.client.post(f'{self.repository["pulp_href"]}untag/', params)

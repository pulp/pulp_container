# # coding=utf-8
"""Tests that recursively remove container content from repositories."""
import unittest

from pulp_smash import api, config
from pulp_smash.pulp3.utils import gen_repo, sync

from pulp_container.tests.functional.constants import (
    CONTAINER_TAG_PATH,
    CONTAINER_REMOTE_PATH,
    CONTAINER_REPO_PATH,
    DOCKERHUB_PULP_FIXTURE_1,
)
from pulp_container.tests.functional.utils import gen_container_remote


class TestRecursiveRemove(unittest.TestCase):
    """
    Test recursively removing container content from a repository.

    This test targets the follow feature:
    https://pulp.plan.io/issues/5179
    """

    @classmethod
    def setUpClass(cls):
        """Sync pulp/test-fixture-1 so we can copy content from it."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)
        cls.from_repo = cls.client.post(CONTAINER_REPO_PATH, gen_repo())
        remote_data = gen_container_remote(upstream_name=DOCKERHUB_PULP_FIXTURE_1)
        cls.remote = cls.client.post(CONTAINER_REMOTE_PATH, remote_data)
        sync(cls.cfg, cls.remote, cls.from_repo)
        latest_version = cls.client.get(cls.from_repo['pulp_href'])['latest_version_href']
        cls.latest_from_version = "repository_version={version}".format(version=latest_version)

    def setUp(self):
        """Create an empty repository to copy into."""
        self.to_repo = self.client.post(CONTAINER_REPO_PATH, gen_repo())
        self.CONTAINER_RECURSIVE_REMOVE_PATH = f'{self.to_repo["pulp_href"]}remove/'
        self.CONTAINER_RECURSIVE_ADD_PATH = f'{self.to_repo["pulp_href"]}add/'
        self.addCleanup(self.client.delete, self.to_repo['pulp_href'])

    @classmethod
    def tearDownClass(cls):
        """Delete things made in setUpClass. addCleanup feature does not work with setupClass."""
        cls.client.delete(cls.from_repo['pulp_href'])
        cls.client.delete(cls.remote['pulp_href'])

    def test_repository_only_no_latest_version(self):
        """Do not create a new version, when there is nothing to remove."""
        self.client.post(self.CONTAINER_RECURSIVE_REMOVE_PATH)
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        self.assertIsNone(latest_version_href)

    def test_manifest_recursion(self):
        """Add a manifest and its related blobs."""
        manifest_a = self.client.get("{unit_path}?{filters}".format(
            unit_path=CONTAINER_TAG_PATH,
            filters="name=manifest_a&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['tagged_manifest']
        self.client.post(
            self.CONTAINER_RECURSIVE_ADD_PATH,
            {'content_units': [manifest_a]})
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)

        # Ensure test begins in the correct state
        self.assertFalse('container.tag' in latest['content_summary']['added'])
        self.assertEqual(latest['content_summary']['added']['container.manifest']['count'], 1)
        self.assertEqual(latest['content_summary']['added']['container.blob']['count'], 2)

        # Actual test
        self.client.post(
            self.CONTAINER_RECURSIVE_REMOVE_PATH,
            {'content_units': [manifest_a]})
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)
        self.assertFalse('container.tag' in latest['content_summary']['removed'])
        self.assertEqual(latest['content_summary']['removed']['container.manifest']['count'], 1)
        self.assertEqual(latest['content_summary']['removed']['container.blob']['count'], 2)

    def test_manifest_list_recursion(self):
        """Add a Manifest List, related manifests, and related blobs."""
        ml_i = self.client.get("{unit_path}?{filters}".format(
            unit_path=CONTAINER_TAG_PATH,
            filters="name=ml_i&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['tagged_manifest']
        self.client.post(
            self.CONTAINER_RECURSIVE_ADD_PATH,
            {'content_units': [ml_i]})
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)

        # Ensure test begins in the correct state
        self.assertFalse('container.tag' in latest['content_summary']['added'])
        self.assertEqual(latest['content_summary']['added']['container.manifest']['count'], 3)
        self.assertEqual(latest['content_summary']['added']['container.blob']['count'], 4)

        # Actual test
        self.client.post(
            self.CONTAINER_RECURSIVE_REMOVE_PATH,
            {'content_units': [ml_i]})
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)
        self.assertFalse('container.tag' in latest['content_summary']['removed'])
        self.assertEqual(latest['content_summary']['removed']['container.manifest']['count'], 3)
        self.assertEqual(latest['content_summary']['removed']['container.blob']['count'], 4)

    def test_tagged_manifest_list_recursion(self):
        """Add a tagged manifest list, and its related manifests and blobs."""
        ml_i_tag = self.client.get("{unit_path}?{filters}".format(
            unit_path=CONTAINER_TAG_PATH,
            filters="name=ml_i&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['pulp_href']
        self.client.post(
            self.CONTAINER_RECURSIVE_ADD_PATH,
            {'content_units': [ml_i_tag]})
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)

        # Ensure test begins in the correct state
        self.assertEqual(latest['content_summary']['added']['container.tag']['count'], 1)
        self.assertEqual(latest['content_summary']['added']['container.manifest']['count'], 3)
        self.assertEqual(latest['content_summary']['added']['container.blob']['count'], 4)

        # Actual test
        self.client.post(
            self.CONTAINER_RECURSIVE_REMOVE_PATH,
            {'content_units': [ml_i_tag]})
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)
        self.assertEqual(latest['content_summary']['removed']['container.tag']['count'], 1)
        self.assertEqual(latest['content_summary']['removed']['container.manifest']['count'], 3)
        self.assertEqual(latest['content_summary']['removed']['container.blob']['count'], 4)

    def test_tagged_manifest_recursion(self):
        """Add a tagged manifest and its related blobs."""
        manifest_a_tag = self.client.get("{unit_path}?{filters}".format(
            unit_path=CONTAINER_TAG_PATH,
            filters="name=manifest_a&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['pulp_href']
        self.client.post(
            self.CONTAINER_RECURSIVE_ADD_PATH,
            {'content_units': [manifest_a_tag]})
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)

        # Ensure valid starting state
        self.assertEqual(latest['content_summary']['added']['container.tag']['count'], 1)
        self.assertEqual(latest['content_summary']['added']['container.manifest']['count'], 1)
        self.assertEqual(latest['content_summary']['added']['container.blob']['count'], 2)

        # Actual test
        self.client.post(
            self.CONTAINER_RECURSIVE_REMOVE_PATH,
            {'content_units': [manifest_a_tag]})
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)

        self.assertEqual(latest['content_summary']['removed']['container.tag']['count'], 1)
        self.assertEqual(latest['content_summary']['removed']['container.manifest']['count'], 1)
        self.assertEqual(latest['content_summary']['removed']['container.blob']['count'], 2)

    def test_manifests_shared_blobs(self):
        """Starting with 2 manifests that share blobs, remove one of them."""
        manifest_a = self.client.get("{unit_path}?{filters}".format(
            unit_path=CONTAINER_TAG_PATH,
            filters="name=manifest_a&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['tagged_manifest']
        manifest_e = self.client.get("{unit_path}?{filters}".format(
            unit_path=CONTAINER_TAG_PATH,
            filters="name=manifest_e&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['tagged_manifest']
        self.client.post(
            self.CONTAINER_RECURSIVE_ADD_PATH,
            {'content_units': [manifest_a, manifest_e]})
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)
        # Ensure valid starting state
        self.assertFalse('container.tag' in latest['content_summary']['added'])
        self.assertEqual(latest['content_summary']['added']['container.manifest']['count'], 2)
        # manifest_a has 1 blob, 1 config blob, and manifest_e has 2 blob 1 config blob
        # manifest_a blob is shared with manifest_e
        self.assertEqual(latest['content_summary']['added']['container.blob']['count'], 4)

        # Actual test
        self.client.post(
            self.CONTAINER_RECURSIVE_REMOVE_PATH,
            {'content_units': [manifest_e]})
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)
        self.assertFalse('container.tag' in latest['content_summary']['removed'])
        self.assertEqual(latest['content_summary']['removed']['container.manifest']['count'], 1)
        # Despite having 3 blobs, only 2 are removed, 1 is shared with manifest_a.
        self.assertEqual(latest['content_summary']['removed']['container.blob']['count'], 2)

    def test_manifest_lists_shared_manifests(self):
        """Starting with 2 manifest lists that share a manifest, remove one of them."""
        ml_i = self.client.get("{unit_path}?{filters}".format(
            unit_path=CONTAINER_TAG_PATH,
            filters="name=ml_i&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['tagged_manifest']
        # Shares 1 manifest with ml_i
        ml_iii = self.client.get("{unit_path}?{filters}".format(
            unit_path=CONTAINER_TAG_PATH,
            filters="name=ml_iii&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['tagged_manifest']
        self.client.post(
            self.CONTAINER_RECURSIVE_ADD_PATH,
            {'content_units': [ml_i, ml_iii]})
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)
        # Ensure valid starting state
        self.assertFalse('container.tag' in latest['content_summary']['added'])
        # 2 manifest lists, each with 2 manifests, 1 manifest shared
        self.assertEqual(latest['content_summary']['added']['container.manifest']['count'], 5)
        self.assertEqual(latest['content_summary']['added']['container.blob']['count'], 6)

        # Actual test
        self.client.post(
            self.CONTAINER_RECURSIVE_REMOVE_PATH,
            {'content_units': [ml_iii]})
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)
        self.assertFalse('container.tag' in latest['content_summary']['removed'])
        # 1 manifest list, 1 manifest
        self.assertEqual(latest['content_summary']['removed']['container.manifest']['count'], 2)
        self.assertEqual(latest['content_summary']['removed']['container.blob']['count'], 2)

    def test_many_tagged_manifest_lists(self):
        """Add several Manifest List, related manifests, and related blobs."""
        ml_i_tag = self.client.get("{unit_path}?{filters}".format(
            unit_path=CONTAINER_TAG_PATH,
            filters="name=ml_i&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['pulp_href']
        ml_ii_tag = self.client.get("{unit_path}?{filters}".format(
            unit_path=CONTAINER_TAG_PATH,
            filters="name=ml_ii&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['pulp_href']
        ml_iii_tag = self.client.get("{unit_path}?{filters}".format(
            unit_path=CONTAINER_TAG_PATH,
            filters="name=ml_iii&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['pulp_href']
        ml_iv_tag = self.client.get("{unit_path}?{filters}".format(
            unit_path=CONTAINER_TAG_PATH,
            filters="name=ml_iv&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['pulp_href']
        self.client.post(
            self.CONTAINER_RECURSIVE_ADD_PATH,
            {
                'content_units': [ml_i_tag, ml_ii_tag, ml_iii_tag, ml_iv_tag]
            }
        )
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)

        self.assertEqual(latest['content_summary']['added']['container.tag']['count'], 4)
        self.assertEqual(latest['content_summary']['added']['container.manifest']['count'], 9)
        self.assertEqual(latest['content_summary']['added']['container.blob']['count'], 10)

        self.client.post(
            self.CONTAINER_RECURSIVE_REMOVE_PATH,
            {
                'content_units': [ml_i_tag, ml_ii_tag, ml_iii_tag, ml_iv_tag]
            }
        )
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)

        self.assertEqual(latest['content_summary']['removed']['container.tag']['count'], 4)
        self.assertEqual(latest['content_summary']['removed']['container.manifest']['count'], 9)
        self.assertEqual(latest['content_summary']['removed']['container.blob']['count'], 10)

    def test_cannot_remove_tagged_manifest(self):
        """
        Try to remove a manifest (without removing tag). Creates a new version, but nothing removed.
        """
        manifest_a_tag = self.client.get("{unit_path}?{filters}".format(
            unit_path=CONTAINER_TAG_PATH,
            filters="name=manifest_a&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]
        self.client.post(
            self.CONTAINER_RECURSIVE_ADD_PATH,
            {
                'content_units': [manifest_a_tag['pulp_href']]
            }
        )
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)
        self.assertEqual(latest['content_summary']['added']['container.tag']['count'], 1)
        self.assertEqual(latest['content_summary']['added']['container.manifest']['count'], 1)
        self.assertEqual(latest['content_summary']['added']['container.blob']['count'], 2)

        self.client.post(
            self.CONTAINER_RECURSIVE_REMOVE_PATH,
            {
                'content_units': [manifest_a_tag['tagged_manifest']]
            }
        )

        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)
        for content_type in ['container.tag', 'container.manifest', 'container.blob']:
            self.assertFalse(content_type in latest['content_summary']['removed'], msg=content_type)

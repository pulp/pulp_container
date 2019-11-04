# # coding=utf-8
"""Tests that recursively remove docker content from repositories."""
import unittest

from pulp_smash import api, config
from pulp_smash.pulp3.utils import gen_repo, sync
from requests.exceptions import HTTPError

from pulp_docker.tests.functional.constants import (
    DOCKER_TAG_PATH,
    DOCKER_REMOTE_PATH,
    DOCKER_REPO_PATH,
    DOCKER_RECURSIVE_ADD_PATH,
    DOCKER_RECURSIVE_REMOVE_PATH,
    DOCKERHUB_PULP_FIXTURE_1,
)
from pulp_docker.tests.functional.utils import gen_docker_remote


class TestRecursiveRemove(unittest.TestCase):
    """
    Test recursively removing docker content from a repository.

    This test targets the follow feature:
    https://pulp.plan.io/issues/5179
    """

    @classmethod
    def setUpClass(cls):
        """Sync pulp/test-fixture-1 so we can copy content from it."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)
        cls.from_repo = cls.client.post(DOCKER_REPO_PATH, gen_repo())
        remote_data = gen_docker_remote(upstream_name=DOCKERHUB_PULP_FIXTURE_1)
        cls.remote = cls.client.post(DOCKER_REMOTE_PATH, remote_data)
        sync(cls.cfg, cls.remote, cls.from_repo)
        latest_version = cls.client.get(cls.from_repo['pulp_href'])['latest_version_href']
        cls.latest_from_version = "repository_version={version}".format(version=latest_version)

    def setUp(self):
        """Create an empty repository to copy into."""
        self.to_repo = self.client.post(DOCKER_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, self.to_repo['pulp_href'])

    @classmethod
    def tearDownClass(cls):
        """Delete things made in setUpClass. addCleanup feature does not work with setupClass."""
        cls.client.delete(cls.from_repo['pulp_href'])
        cls.client.delete(cls.remote['pulp_href'])

    def test_missing_repository_argument(self):
        """Ensure Repository argument is required."""
        with self.assertRaises(HTTPError) as context:
            self.client.post(DOCKER_RECURSIVE_ADD_PATH)
        self.assertEqual(context.exception.response.status_code, 400)

    def test_repository_only(self):
        """Passing only a repository creates a new version."""
        # Create a new version, repository must have latest version to be valid.
        self.client.post(DOCKER_RECURSIVE_ADD_PATH, {'repository': self.to_repo['pulp_href']})
        after_add_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']

        # Actual test
        self.client.post(DOCKER_RECURSIVE_REMOVE_PATH, {'repository': self.to_repo['pulp_href']})
        after_remove_version_href = self.client.get(
            self.to_repo['pulp_href'])['latest_version_href']
        self.assertNotEqual(after_add_version_href, after_remove_version_href)
        latest = self.client.get(after_remove_version_href)
        for content_type in ['docker.tag', 'docker.manifest', 'docker.blob']:
            self.assertFalse(content_type in latest['content_summary']['removed'], msg=content_type)

    def test_repository_only_no_latest_version(self):
        """Create a new version, even when there is nothing to remove."""
        self.client.post(DOCKER_RECURSIVE_REMOVE_PATH, {'repository': self.to_repo['pulp_href']})
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        self.assertIsNotNone(latest_version_href)
        latest = self.client.get(latest_version_href)
        for content_type in ['docker.tag', 'docker.manifest', 'docker.blob']:
            self.assertFalse(content_type in latest['content_summary']['removed'], msg=content_type)

    def test_manifest_recursion(self):
        """Add a manifest and its related blobs."""
        manifest_a = self.client.get("{unit_path}?{filters}".format(
            unit_path=DOCKER_TAG_PATH,
            filters="name=manifest_a&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['tagged_manifest']
        self.client.post(
            DOCKER_RECURSIVE_ADD_PATH,
            {'repository': self.to_repo['pulp_href'], 'content_units': [manifest_a]})
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)

        # Ensure test begins in the correct state
        self.assertFalse('docker.tag' in latest['content_summary']['added'])
        self.assertEqual(latest['content_summary']['added']['docker.manifest']['count'], 1)
        self.assertEqual(latest['content_summary']['added']['docker.blob']['count'], 2)

        # Actual test
        self.client.post(
            DOCKER_RECURSIVE_REMOVE_PATH,
            {'repository': self.to_repo['pulp_href'], 'content_units': [manifest_a]})
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)
        self.assertFalse('docker.tag' in latest['content_summary']['removed'])
        self.assertEqual(latest['content_summary']['removed']['docker.manifest']['count'], 1)
        self.assertEqual(latest['content_summary']['removed']['docker.blob']['count'], 2)

    def test_manifest_list_recursion(self):
        """Add a Manifest List, related manifests, and related blobs."""
        ml_i = self.client.get("{unit_path}?{filters}".format(
            unit_path=DOCKER_TAG_PATH,
            filters="name=ml_i&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['tagged_manifest']
        self.client.post(
            DOCKER_RECURSIVE_ADD_PATH,
            {'repository': self.to_repo['pulp_href'], 'content_units': [ml_i]})
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)

        # Ensure test begins in the correct state
        self.assertFalse('docker.tag' in latest['content_summary']['added'])
        self.assertEqual(latest['content_summary']['added']['docker.manifest']['count'], 3)
        self.assertEqual(latest['content_summary']['added']['docker.blob']['count'], 4)

        # Actual test
        self.client.post(
            DOCKER_RECURSIVE_REMOVE_PATH,
            {'repository': self.to_repo['pulp_href'], 'content_units': [ml_i]})
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)
        self.assertFalse('docker.tag' in latest['content_summary']['removed'])
        self.assertEqual(latest['content_summary']['removed']['docker.manifest']['count'], 3)
        self.assertEqual(latest['content_summary']['removed']['docker.blob']['count'], 4)

    def test_tagged_manifest_list_recursion(self):
        """Add a tagged manifest list, and its related manifests and blobs."""
        ml_i_tag = self.client.get("{unit_path}?{filters}".format(
            unit_path=DOCKER_TAG_PATH,
            filters="name=ml_i&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['pulp_href']
        self.client.post(
            DOCKER_RECURSIVE_ADD_PATH,
            {'repository': self.to_repo['pulp_href'], 'content_units': [ml_i_tag]})
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)

        # Ensure test begins in the correct state
        self.assertEqual(latest['content_summary']['added']['docker.tag']['count'], 1)
        self.assertEqual(latest['content_summary']['added']['docker.manifest']['count'], 3)
        self.assertEqual(latest['content_summary']['added']['docker.blob']['count'], 4)

        # Actual test
        self.client.post(
            DOCKER_RECURSIVE_REMOVE_PATH,
            {'repository': self.to_repo['pulp_href'], 'content_units': [ml_i_tag]})
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)
        self.assertEqual(latest['content_summary']['removed']['docker.tag']['count'], 1)
        self.assertEqual(latest['content_summary']['removed']['docker.manifest']['count'], 3)
        self.assertEqual(latest['content_summary']['removed']['docker.blob']['count'], 4)

    def test_tagged_manifest_recursion(self):
        """Add a tagged manifest and its related blobs."""
        manifest_a_tag = self.client.get("{unit_path}?{filters}".format(
            unit_path=DOCKER_TAG_PATH,
            filters="name=manifest_a&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['pulp_href']
        self.client.post(
            DOCKER_RECURSIVE_ADD_PATH,
            {'repository': self.to_repo['pulp_href'], 'content_units': [manifest_a_tag]})
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)

        # Ensure valid starting state
        self.assertEqual(latest['content_summary']['added']['docker.tag']['count'], 1)
        self.assertEqual(latest['content_summary']['added']['docker.manifest']['count'], 1)
        self.assertEqual(latest['content_summary']['added']['docker.blob']['count'], 2)

        # Actual test
        self.client.post(
            DOCKER_RECURSIVE_REMOVE_PATH,
            {'repository': self.to_repo['pulp_href'], 'content_units': [manifest_a_tag]})
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)

        self.assertEqual(latest['content_summary']['removed']['docker.tag']['count'], 1)
        self.assertEqual(latest['content_summary']['removed']['docker.manifest']['count'], 1)
        self.assertEqual(latest['content_summary']['removed']['docker.blob']['count'], 2)

    def test_manifests_shared_blobs(self):
        """Starting with 2 manifests that share blobs, remove one of them."""
        manifest_a = self.client.get("{unit_path}?{filters}".format(
            unit_path=DOCKER_TAG_PATH,
            filters="name=manifest_a&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['tagged_manifest']
        manifest_e = self.client.get("{unit_path}?{filters}".format(
            unit_path=DOCKER_TAG_PATH,
            filters="name=manifest_e&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['tagged_manifest']
        self.client.post(
            DOCKER_RECURSIVE_ADD_PATH,
            {'repository': self.to_repo['pulp_href'], 'content_units': [manifest_a, manifest_e]})
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)
        # Ensure valid starting state
        self.assertFalse('docker.tag' in latest['content_summary']['added'])
        self.assertEqual(latest['content_summary']['added']['docker.manifest']['count'], 2)
        # manifest_a has 1 blob, 1 config blob, and manifest_e has 2 blob 1 config blob
        # manifest_a blob is shared with manifest_e
        self.assertEqual(latest['content_summary']['added']['docker.blob']['count'], 4)

        # Actual test
        self.client.post(
            DOCKER_RECURSIVE_REMOVE_PATH,
            {'repository': self.to_repo['pulp_href'], 'content_units': [manifest_e]})
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)
        self.assertFalse('docker.tag' in latest['content_summary']['removed'])
        self.assertEqual(latest['content_summary']['removed']['docker.manifest']['count'], 1)
        # Despite having 3 blobs, only 2 are removed, 1 is shared with manifest_a.
        self.assertEqual(latest['content_summary']['removed']['docker.blob']['count'], 2)

    def test_manifest_lists_shared_manifests(self):
        """Starting with 2 manifest lists that share a manifest, remove one of them."""
        ml_i = self.client.get("{unit_path}?{filters}".format(
            unit_path=DOCKER_TAG_PATH,
            filters="name=ml_i&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['tagged_manifest']
        # Shares 1 manifest with ml_i
        ml_iii = self.client.get("{unit_path}?{filters}".format(
            unit_path=DOCKER_TAG_PATH,
            filters="name=ml_iii&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['tagged_manifest']
        self.client.post(
            DOCKER_RECURSIVE_ADD_PATH,
            {'repository': self.to_repo['pulp_href'], 'content_units': [ml_i, ml_iii]})
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)
        # Ensure valid starting state
        self.assertFalse('docker.tag' in latest['content_summary']['added'])
        # 2 manifest lists, each with 2 manifests, 1 manifest shared
        self.assertEqual(latest['content_summary']['added']['docker.manifest']['count'], 5)
        self.assertEqual(latest['content_summary']['added']['docker.blob']['count'], 6)

        # Actual test
        self.client.post(
            DOCKER_RECURSIVE_REMOVE_PATH,
            {'repository': self.to_repo['pulp_href'], 'content_units': [ml_iii]})
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)
        self.assertFalse('docker.tag' in latest['content_summary']['removed'])
        # 1 manifest list, 1 manifest
        self.assertEqual(latest['content_summary']['removed']['docker.manifest']['count'], 2)
        self.assertEqual(latest['content_summary']['removed']['docker.blob']['count'], 2)

    def test_many_tagged_manifest_lists(self):
        """Add several Manifest List, related manifests, and related blobs."""
        ml_i_tag = self.client.get("{unit_path}?{filters}".format(
            unit_path=DOCKER_TAG_PATH,
            filters="name=ml_i&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['pulp_href']
        ml_ii_tag = self.client.get("{unit_path}?{filters}".format(
            unit_path=DOCKER_TAG_PATH,
            filters="name=ml_ii&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['pulp_href']
        ml_iii_tag = self.client.get("{unit_path}?{filters}".format(
            unit_path=DOCKER_TAG_PATH,
            filters="name=ml_iii&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['pulp_href']
        ml_iv_tag = self.client.get("{unit_path}?{filters}".format(
            unit_path=DOCKER_TAG_PATH,
            filters="name=ml_iv&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['pulp_href']
        self.client.post(
            DOCKER_RECURSIVE_ADD_PATH,
            {
                'repository': self.to_repo['pulp_href'],
                'content_units': [ml_i_tag, ml_ii_tag, ml_iii_tag, ml_iv_tag]
            }
        )
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)

        self.assertEqual(latest['content_summary']['added']['docker.tag']['count'], 4)
        self.assertEqual(latest['content_summary']['added']['docker.manifest']['count'], 9)
        self.assertEqual(latest['content_summary']['added']['docker.blob']['count'], 10)

        self.client.post(
            DOCKER_RECURSIVE_REMOVE_PATH,
            {
                'repository': self.to_repo['pulp_href'],
                'content_units': [ml_i_tag, ml_ii_tag, ml_iii_tag, ml_iv_tag]
            }
        )
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)

        self.assertEqual(latest['content_summary']['removed']['docker.tag']['count'], 4)
        self.assertEqual(latest['content_summary']['removed']['docker.manifest']['count'], 9)
        self.assertEqual(latest['content_summary']['removed']['docker.blob']['count'], 10)

    def test_cannot_remove_tagged_manifest(self):
        """
        Try to remove a manifest (without removing tag). Creates a new version, but nothing removed.
        """
        manifest_a_tag = self.client.get("{unit_path}?{filters}".format(
            unit_path=DOCKER_TAG_PATH,
            filters="name=manifest_a&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]
        self.client.post(
            DOCKER_RECURSIVE_ADD_PATH,
            {
                'repository': self.to_repo['pulp_href'],
                'content_units': [manifest_a_tag['pulp_href']]
            }
        )
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)
        self.assertEqual(latest['content_summary']['added']['docker.tag']['count'], 1)
        self.assertEqual(latest['content_summary']['added']['docker.manifest']['count'], 1)
        self.assertEqual(latest['content_summary']['added']['docker.blob']['count'], 2)

        self.client.post(
            DOCKER_RECURSIVE_REMOVE_PATH,
            {
                'repository': self.to_repo['pulp_href'],
                'content_units': [manifest_a_tag['tagged_manifest']]
            }
        )

        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)
        for content_type in ['docker.tag', 'docker.manifest', 'docker.blob']:
            self.assertFalse(content_type in latest['content_summary']['removed'], msg=content_type)

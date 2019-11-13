# coding=utf-8
"""Tests that recursively add container content to repositories."""
import unittest

from pulp_smash import api, config
from pulp_smash.pulp3.utils import gen_repo, sync
from requests.exceptions import HTTPError

from pulp_container.tests.functional.constants import (
    CONTAINER_TAG_PATH,
    CONTAINER_REMOTE_PATH,
    CONTAINER_REPO_PATH,
    DOCKERHUB_PULP_FIXTURE_1,
)
from pulp_container.tests.functional.utils import gen_container_remote
from pulp_container.constants import MEDIA_TYPE


class TestManifestCopy(unittest.TestCase):
    """
    Test recursive copy of Manifests into a repository.

    This test targets the follow feature:
    https://pulp.plan.io/issues/3403
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
        self.CONTAINER_MANIFEST_COPY_PATH = f'{self.to_repo["pulp_href"]}copy_manifests/'
        self.addCleanup(self.client.delete, self.to_repo['pulp_href'])

    @classmethod
    def tearDownClass(cls):
        """Delete things made in setUpClass. addCleanup feature does not work with setupClass."""
        cls.client.delete(cls.from_repo['pulp_href'])
        cls.client.delete(cls.remote['pulp_href'])

    def test_missing_repository_argument(self):
        """Ensure source_repository or source_repository_version is required."""
        with self.assertRaises(HTTPError) as context:
            self.client.post(self.CONTAINER_MANIFEST_COPY_PATH)
        self.assertEqual(context.exception.response.status_code, 400)

    def test_empty_source_repository(self):
        """Ensure exception is raised when source_repository does not have latest version."""
        with self.assertRaises(HTTPError) as context:
            self.client.post(
                self.CONTAINER_MANIFEST_COPY_PATH,
                {
                    # to_repo has no versions, use it as source
                    'source_repository': self.to_repo['pulp_href'],
                }
            )
        self.assertEqual(context.exception.response.status_code, 400)

    def test_source_repository_and_source_version(self):
        """Passing source_repository_version and repository returns a 400."""
        with self.assertRaises(HTTPError) as context:
            self.client.post(
                self.CONTAINER_MANIFEST_COPY_PATH,
                {
                    'source_repository': self.from_repo['pulp_href'],
                    'source_repository_version': self.from_repo['latest_version_href'],
                }
            )
        self.assertEqual(context.exception.response.status_code, 400)

    def test_copy_all_manifests(self):
        """Passing only source repository copies all manifests."""
        self.client.post(
            self.CONTAINER_MANIFEST_COPY_PATH,
            {
                'source_repository': self.from_repo['pulp_href'],
            }
        )
        latest_to_repo_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest_from_repo_href = self.client.get(self.from_repo['pulp_href'])['latest_version_href']
        to_repo_content = self.client.get(latest_to_repo_href)['content_summary']['present']
        from_repo_content = self.client.get(latest_from_repo_href)['content_summary']['present']
        for container_type in ['container.manifest', 'container.blob']:
            self.assertEqual(
                to_repo_content[container_type]['count'],
                from_repo_content[container_type]['count'],
                msg=container_type,
            )
        self.assertFalse('container.tag' in to_repo_content)

    def test_copy_all_manifests_from_version(self):
        """Passing only source version copies all manifests."""
        latest_from_repo_href = self.client.get(self.from_repo['pulp_href'])['latest_version_href']
        self.client.post(
            self.CONTAINER_MANIFEST_COPY_PATH,
            {
                'source_repository_version': latest_from_repo_href,
            }
        )
        latest_to_repo_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        to_repo_content = self.client.get(latest_to_repo_href)['content_summary']['present']
        from_repo_content = self.client.get(latest_from_repo_href)['content_summary']['present']
        for container_type in ['container.manifest', 'container.blob']:
            self.assertEqual(
                to_repo_content[container_type]['count'],
                from_repo_content[container_type]['count']
            )
        self.assertFalse('container.tag' in to_repo_content)

    def test_copy_manifest_by_digest(self):
        """Specify a single manifest by digest to copy."""
        manifest_a_href = self.client.get("{unit_path}?{filters}".format(
            unit_path=CONTAINER_TAG_PATH,
            filters="name=manifest_a&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['tagged_manifest']
        manifest_a_digest = self.client.get(manifest_a_href)['digest']
        self.client.post(
            self.CONTAINER_MANIFEST_COPY_PATH,
            {
                'source_repository': self.from_repo['pulp_href'],
                'digests': [manifest_a_digest]
            }
        )
        latest_to_repo_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        to_repo_content = self.client.get(latest_to_repo_href)['content_summary']['present']
        self.assertFalse('container.tag' in to_repo_content)
        self.assertEqual(to_repo_content['container.manifest']['count'], 1)
        # manifest_a has 2 blobs
        self.assertEqual(to_repo_content['container.blob']['count'], 2)

    def test_copy_manifest_by_digest_and_media_type(self):
        """Specify a single manifest by digest to copy."""
        manifest_a_href = self.client.get("{unit_path}?{filters}".format(
            unit_path=CONTAINER_TAG_PATH,
            filters="name=manifest_a&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['tagged_manifest']
        manifest_a_digest = self.client.get(manifest_a_href)['digest']
        self.client.post(
            self.CONTAINER_MANIFEST_COPY_PATH,
            {
                'source_repository': self.from_repo['pulp_href'],
                'digests': [manifest_a_digest],
                'media_types': [MEDIA_TYPE.MANIFEST_V2]
            }
        )
        latest_to_repo_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        to_repo_content = self.client.get(latest_to_repo_href)['content_summary']['present']
        self.assertFalse('container.tag' in to_repo_content)
        self.assertEqual(to_repo_content['container.manifest']['count'], 1)
        # manifest_a has 2 blobs
        self.assertEqual(to_repo_content['container.blob']['count'], 2)

    def test_copy_all_manifest_lists_by_media_type(self):
        """Specify the media_type, to copy all manifest lists."""
        self.client.post(
            self.CONTAINER_MANIFEST_COPY_PATH,
            {
                'source_repository': self.from_repo['pulp_href'],
                'media_types': [MEDIA_TYPE.MANIFEST_LIST]
            }
        )
        latest_to_repo_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        to_repo_content = self.client.get(latest_to_repo_href)['content_summary']['present']
        self.assertFalse('container.tag' in to_repo_content)
        # Fixture has 4 manifest lists, which combined reference 5 manifests
        self.assertEqual(to_repo_content['container.manifest']['count'], 9)
        # each manifest (non-list) has 2 blobs
        self.assertEqual(to_repo_content['container.blob']['count'], 10)

    def test_copy_all_manifests_by_media_type(self):
        """Specify the media_type, to copy all manifest lists."""
        self.client.post(
            self.CONTAINER_MANIFEST_COPY_PATH,
            {
                'source_repository': self.from_repo['pulp_href'],
                'media_types': [MEDIA_TYPE.MANIFEST_V1, MEDIA_TYPE.MANIFEST_V2]
            }
        )
        latest_to_repo_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        to_repo_content = self.client.get(latest_to_repo_href)['content_summary']['present']
        self.assertFalse('container.tag' in to_repo_content)
        # Fixture has 5 manifests that aren't manifest lists
        self.assertEqual(to_repo_content['container.manifest']['count'], 5)
        # each manifest (non-list) has 2 blobs
        self.assertEqual(to_repo_content['container.blob']['count'], 10)

    def test_fail_to_copy_invalid_manifest_media_type(self):
        """Specify the media_type, to copy all manifest lists."""
        with self.assertRaises(HTTPError) as context:
            self.client.post(
                self.CONTAINER_MANIFEST_COPY_PATH,
                {
                    'source_repository': self.from_repo['pulp_href'],
                    'media_types': ['wrongwrongwrong']
                }
            )
        self.assertEqual(context.exception.response.status_code, 400)

    def test_copy_by_digest_with_incorrect_media_type(self):
        """Ensure invalid media type will raise a 400."""
        ml_i_href = self.client.get("{unit_path}?{filters}".format(
            unit_path=CONTAINER_TAG_PATH,
            filters="name=ml_i&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['tagged_manifest']
        ml_i_digest = self.client.get(ml_i_href)['digest']
        self.client.post(
            self.CONTAINER_MANIFEST_COPY_PATH,
            {
                'source_repository': self.from_repo['pulp_href'],
                'digests': [ml_i_digest],
                'media_types': [MEDIA_TYPE.MANIFEST_V2]
            }
        )
        latest_to_repo_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        # Assert no version created
        self.assertIsNone(latest_to_repo_href)

    def test_copy_multiple_manifests_by_digest(self):
        """Specify digests to copy."""
        ml_i_href = self.client.get("{unit_path}?{filters}".format(
            unit_path=CONTAINER_TAG_PATH,
            filters="name=ml_i&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['tagged_manifest']
        ml_i_digest = self.client.get(ml_i_href)['digest']
        ml_ii_href = self.client.get("{unit_path}?{filters}".format(
            unit_path=CONTAINER_TAG_PATH,
            filters="name=ml_ii&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['tagged_manifest']
        ml_ii_digest = self.client.get(ml_ii_href)['digest']
        self.client.post(
            self.CONTAINER_MANIFEST_COPY_PATH,
            {
                'source_repository': self.from_repo['pulp_href'],
                'digests': [ml_i_digest, ml_ii_digest]
            }
        )
        latest_to_repo_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        to_repo_content = self.client.get(latest_to_repo_href)['content_summary']['present']
        self.assertFalse('container.tag' in to_repo_content)
        # each manifest list is a manifest and references 2 other manifests
        self.assertEqual(to_repo_content['container.manifest']['count'], 6)
        # each referenced manifest has 2 blobs
        self.assertEqual(to_repo_content['container.blob']['count'], 8)

    def test_copy_manifests_by_digest_empty_list(self):
        """Passing an empty list copies no manifests."""
        self.client.post(
            self.CONTAINER_MANIFEST_COPY_PATH,
            {
                'source_repository': self.from_repo['pulp_href'],
                'digests': []
            }
        )
        latest_to_repo_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        # Assert a new version was not created
        self.assertIsNone(latest_to_repo_href)


class TestTagCopy(unittest.TestCase):
    """Test recursive copy of tags content to a repository."""

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
        self.CONTAINER_TAG_COPY_PATH = f'{self.to_repo["pulp_href"]}copy_tags/'
        self.addCleanup(self.client.delete, self.to_repo['pulp_href'])

    @classmethod
    def tearDownClass(cls):
        """Delete things made in setUpClass. addCleanup feature does not work with setupClass."""
        cls.client.delete(cls.from_repo['pulp_href'])
        cls.client.delete(cls.remote['pulp_href'])

    def test_missing_repository_argument(self):
        """Ensure source_repository or source_repository_version is required."""
        with self.assertRaises(HTTPError):
            self.client.post(self.CONTAINER_TAG_COPY_PATH)

    def test_empty_source_repository(self):
        """Ensure exception is raised when source_repository does not have latest version."""
        with self.assertRaises(HTTPError):
            self.client.post(
                self.CONTAINER_TAG_COPY_PATH,
                {
                    # to_repo has no versions, use it as source
                    'source_repository': self.to_repo['pulp_href'],
                }
            )

    def test_source_repository_and_source_version(self):
        """Passing both source_repository_version and source_repository returns a 400."""
        with self.assertRaises(HTTPError) as context:
            self.client.post(
                self.CONTAINER_TAG_COPY_PATH,
                {
                    'source_repository': self.from_repo['pulp_href'],
                    'source_repository_version': self.from_repo['latest_version_href'],
                }
            )
        self.assertEqual(context.exception.response.status_code, 400)

    def test_copy_all_tags(self):
        """Passing only source and destination repositories copies all tags."""
        self.client.post(
            self.CONTAINER_TAG_COPY_PATH,
            {
                'source_repository': self.from_repo['pulp_href'],
            }
        )
        latest_to_repo_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest_from_repo_href = self.client.get(self.from_repo['pulp_href'])['latest_version_href']
        to_repo_content = self.client.get(latest_to_repo_href)['content_summary']['present']
        from_repo_content = self.client.get(latest_from_repo_href)['content_summary']['present']
        for container_type in ['container.tag', 'container.manifest', 'container.blob']:
            self.assertEqual(
                to_repo_content[container_type]['count'],
                from_repo_content[container_type]['count'],
                msg=container_type,
            )

    def test_copy_all_tags_from_version(self):
        """Passing only source version and destination repositories copies all tags."""
        latest_from_repo_href = self.client.get(self.from_repo['pulp_href'])['latest_version_href']
        self.client.post(
            self.CONTAINER_TAG_COPY_PATH,
            {
                'source_repository_version': latest_from_repo_href,
            }
        )
        latest_to_repo_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        to_repo_content = self.client.get(latest_to_repo_href)['content_summary']['present']
        from_repo_content = self.client.get(latest_from_repo_href)['content_summary']['present']
        for container_type in ['container.tag', 'container.manifest', 'container.blob']:
            self.assertEqual(
                to_repo_content[container_type]['count'],
                from_repo_content[container_type]['count'],
                msg=container_type,
            )

    def test_copy_tags_by_name(self):
        """Copy tags in destination repo that match name."""
        self.client.post(
            self.CONTAINER_TAG_COPY_PATH,
            {
                'source_repository': self.from_repo['pulp_href'],
                'names': ['ml_i', 'manifest_c']
            }
        )
        latest_to_repo_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        to_repo_content = self.client.get(latest_to_repo_href)['content_summary']['present']
        self.assertEqual(to_repo_content['container.tag']['count'], 2)
        # ml_i has 1 manifest list, 2 manifests, manifest_c has 1 manifest
        self.assertEqual(to_repo_content['container.manifest']['count'], 4)
        # each manifest (not manifest list) has 2 blobs
        self.assertEqual(to_repo_content['container.blob']['count'], 6)

    def test_copy_tags_by_name_empty_list(self):
        """Passing an empty list of names copies nothing."""
        self.client.post(
            self.CONTAINER_TAG_COPY_PATH,
            {
                'source_repository': self.from_repo['pulp_href'],
                'names': []
            }
        )
        latest_to_repo_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        # Assert a new version was not created
        self.assertIsNone(latest_to_repo_href)

    def test_copy_tags_with_conflicting_names(self):
        """If tag names are already present in a repository, the conflicting tags are removed."""
        self.client.post(
            self.CONTAINER_TAG_COPY_PATH,
            {
                'source_repository': self.from_repo['pulp_href'],
            }
        )
        # Same call
        self.client.post(
            self.CONTAINER_TAG_COPY_PATH,
            {
                'source_repository': self.from_repo['pulp_href'],
            }
        )
        latest_to_repo_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest_from_repo_href = self.client.get(self.from_repo['pulp_href'])['latest_version_href']
        to_repo_content = self.client.get(latest_to_repo_href)['content_summary']
        from_repo_content = self.client.get(latest_from_repo_href)['content_summary']
        for container_type in ['container.tag', 'container.manifest', 'container.blob']:
            self.assertEqual(
                to_repo_content['present'][container_type]['count'],
                from_repo_content['present'][container_type]['count']
            )

        self.assertEqual(
            to_repo_content['added']['container.tag']['count'],
            from_repo_content['present']['container.tag']['count']
        )
        self.assertEqual(
            to_repo_content['removed']['container.tag']['count'],
            from_repo_content['present']['container.tag']['count']
        )


class TestRecursiveAdd(unittest.TestCase):
    """Test recursively adding container content to a repository."""

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
        self.CONTAINER_RECURSIVE_ADD_PATH = f'{self.to_repo["pulp_href"]}add/'
        self.addCleanup(self.client.delete, self.to_repo['pulp_href'])

    @classmethod
    def tearDownClass(cls):
        """Delete things made in setUpClass. addCleanup feature does not work with setupClass."""
        cls.client.delete(cls.from_repo['pulp_href'])
        cls.client.delete(cls.remote['pulp_href'])

    def test_repository_only(self):
        """Passing only a repository does not create a new version."""
        self.client.post(self.CONTAINER_RECURSIVE_ADD_PATH)
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        self.assertEqual(latest_version_href, self.to_repo['latest_version_href'])

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

        # No tags added
        self.assertFalse('container.manifest-tag' in latest['content_summary']['added'])

        # manifest a has 2 blobs
        self.assertEqual(latest['content_summary']['added']['container.manifest']['count'], 1)
        self.assertEqual(latest['content_summary']['added']['container.blob']['count'], 2)

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

        # No tags added
        self.assertFalse('container.tag' in latest['content_summary']['added'])
        # 1 manifest list 2 manifests
        self.assertEqual(latest['content_summary']['added']['container.manifest']['count'], 3)

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
        self.assertEqual(latest['content_summary']['added']['container.tag']['count'], 1)
        # 1 manifest list 2 manifests
        self.assertEqual(latest['content_summary']['added']['container.manifest']['count'], 3)
        self.assertEqual(latest['content_summary']['added']['container.blob']['count'], 4)

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

        self.assertEqual(latest['content_summary']['added']['container.tag']['count'], 1)
        self.assertEqual(latest['content_summary']['added']['container.manifest']['count'], 1)
        self.assertEqual(latest['content_summary']['added']['container.blob']['count'], 2)

    def test_tag_replacement(self):
        """Add a tagged manifest to a repo with a tag of that name already in place."""
        manifest_a_tag = self.client.get("{unit_path}?{filters}".format(
            unit_path=CONTAINER_TAG_PATH,
            filters="name=manifest_a&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['pulp_href']

        # Add manifest_b to the repo
        manifest_b = self.client.get("{unit_path}?{filters}".format(
            unit_path=CONTAINER_TAG_PATH,
            filters="name=manifest_b&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['tagged_manifest']
        manifest_b_digest = self.client.get(manifest_b)['digest']
        self.client.post(
            self.CONTAINER_RECURSIVE_ADD_PATH,
            {'content_units': [manifest_b]})
        # Tag manifest_b as `manifest_a`
        params = {
            'tag': "manifest_a",
            'digest': manifest_b_digest
        }
        self.client.post(f'{self.to_repo["pulp_href"]}tag/', params)

        # Now add original manifest_a tag to the repo, which should remove the
        # new manifest_a tag, but leave the tagged manifest (manifest_b)
        self.client.post(
            self.CONTAINER_RECURSIVE_ADD_PATH,
            {'content_units': [manifest_a_tag]})

        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)
        self.assertEqual(latest['content_summary']['added']['container.tag']['count'], 1)
        self.assertEqual(latest['content_summary']['removed']['container.tag']['count'], 1)
        self.assertFalse('container.manifest' in latest['content_summary']['removed'])
        self.assertFalse('container.blob' in latest['content_summary']['removed'])

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

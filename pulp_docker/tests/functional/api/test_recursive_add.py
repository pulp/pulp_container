# coding=utf-8
"""Tests that recursively add docker content to repositories."""
import unittest

from pulp_smash import api, config
from pulp_smash.pulp3.utils import gen_repo, sync
from requests.exceptions import HTTPError

from pulp_docker.tests.functional.constants import (
    DOCKER_MANIFEST_COPY_PATH,
    DOCKER_TAG_PATH,
    DOCKER_TAG_COPY_PATH,
    DOCKER_TAGGING_PATH,
    DOCKER_REMOTE_PATH,
    DOCKER_REPO_PATH,
    DOCKER_RECURSIVE_ADD_PATH,
    DOCKERHUB_PULP_FIXTURE_1,
)
from pulp_docker.tests.functional.utils import gen_docker_remote
from pulp_docker.constants import MEDIA_TYPE


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
        """Ensure source_repository or source_repository_version is required."""
        with self.assertRaises(HTTPError) as context:
            self.client.post(DOCKER_MANIFEST_COPY_PATH)
        self.assertEqual(context.exception.response.status_code, 400)

        with self.assertRaises(HTTPError) as context:
            self.client.post(
                DOCKER_MANIFEST_COPY_PATH,
                {'source_repository': self.from_repo['pulp_href']}
            )
        self.assertEqual(context.exception.response.status_code, 400)

        with self.assertRaises(HTTPError) as context:
            self.client.post(
                DOCKER_MANIFEST_COPY_PATH,
                {'source_repository_version': self.from_repo['latest_version_href']}
            )
        self.assertEqual(context.exception.response.status_code, 400)

        with self.assertRaises(HTTPError) as context:
            self.client.post(
                DOCKER_RECURSIVE_ADD_PATH,
                {'destination_repository': self.to_repo['pulp_href']}
            )
        self.assertEqual(context.exception.response.status_code, 400)

    def test_empty_source_repository(self):
        """Ensure exception is raised when source_repository does not have latest version."""
        with self.assertRaises(HTTPError) as context:
            self.client.post(
                DOCKER_MANIFEST_COPY_PATH,
                {
                    # to_repo has no versions, use it as source
                    'source_repository': self.to_repo['pulp_href'],
                    'destination_repository': self.from_repo['pulp_href'],
                }
            )
        self.assertEqual(context.exception.response.status_code, 400)

    def test_source_repository_and_source_version(self):
        """Passing source_repository_version and repository returns a 400."""
        with self.assertRaises(HTTPError) as context:
            self.client.post(
                DOCKER_TAG_COPY_PATH,
                {
                    'source_repository': self.from_repo['pulp_href'],
                    'source_repository_version': self.from_repo['latest_version_href'],
                    'destination_repository': self.to_repo['pulp_href']
                }
            )
        self.assertEqual(context.exception.response.status_code, 400)

    def test_copy_all_manifests(self):
        """Passing only source and destination repositories copies all manifests."""
        self.client.post(
            DOCKER_MANIFEST_COPY_PATH,
            {
                'source_repository': self.from_repo['pulp_href'],
                'destination_repository': self.to_repo['pulp_href']
            }
        )
        latest_to_repo_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest_from_repo_href = self.client.get(self.from_repo['pulp_href'])['latest_version_href']
        to_repo_content = self.client.get(latest_to_repo_href)['content_summary']['present']
        from_repo_content = self.client.get(latest_from_repo_href)['content_summary']['present']
        for docker_type in ['docker.manifest', 'docker.blob']:
            self.assertEqual(
                to_repo_content[docker_type]['count'],
                from_repo_content[docker_type]['count'],
                msg=docker_type,
            )
        self.assertFalse('docker.tag' in to_repo_content)

    def test_copy_all_manifests_from_version(self):
        """Passing only source version and destination repositories copies all manifests."""
        latest_from_repo_href = self.client.get(self.from_repo['pulp_href'])['latest_version_href']
        self.client.post(
            DOCKER_MANIFEST_COPY_PATH,
            {
                'source_repository_version': latest_from_repo_href,
                'destination_repository': self.to_repo['pulp_href']
            }
        )
        latest_to_repo_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        to_repo_content = self.client.get(latest_to_repo_href)['content_summary']['present']
        from_repo_content = self.client.get(latest_from_repo_href)['content_summary']['present']
        for docker_type in ['docker.manifest', 'docker.blob']:
            self.assertEqual(
                to_repo_content[docker_type]['count'],
                from_repo_content[docker_type]['count']
            )
        self.assertFalse('docker.tag' in to_repo_content)

    def test_copy_manifest_by_digest(self):
        """Specify a single manifest by digest to copy."""
        manifest_a_href = self.client.get("{unit_path}?{filters}".format(
            unit_path=DOCKER_TAG_PATH,
            filters="name=manifest_a&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['tagged_manifest']
        manifest_a_digest = self.client.get(manifest_a_href)['digest']
        self.client.post(
            DOCKER_MANIFEST_COPY_PATH,
            {
                'source_repository': self.from_repo['pulp_href'],
                'destination_repository': self.to_repo['pulp_href'],
                'digests': [manifest_a_digest]
            }
        )
        latest_to_repo_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        to_repo_content = self.client.get(latest_to_repo_href)['content_summary']['present']
        self.assertFalse('docker.tag' in to_repo_content)
        self.assertEqual(to_repo_content['docker.manifest']['count'], 1)
        # manifest_a has 2 blobs
        self.assertEqual(to_repo_content['docker.blob']['count'], 2)

    def test_copy_manifest_by_digest_and_media_type(self):
        """Specify a single manifest by digest to copy."""
        manifest_a_href = self.client.get("{unit_path}?{filters}".format(
            unit_path=DOCKER_TAG_PATH,
            filters="name=manifest_a&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['tagged_manifest']
        manifest_a_digest = self.client.get(manifest_a_href)['digest']
        self.client.post(
            DOCKER_MANIFEST_COPY_PATH,
            {
                'source_repository': self.from_repo['pulp_href'],
                'destination_repository': self.to_repo['pulp_href'],
                'digests': [manifest_a_digest],
                'media_types': [MEDIA_TYPE.MANIFEST_V2]
            }
        )
        latest_to_repo_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        to_repo_content = self.client.get(latest_to_repo_href)['content_summary']['present']
        self.assertFalse('docker.tag' in to_repo_content)
        self.assertEqual(to_repo_content['docker.manifest']['count'], 1)
        # manifest_a has 2 blobs
        self.assertEqual(to_repo_content['docker.blob']['count'], 2)

    def test_copy_all_manifest_lists_by_media_type(self):
        """Specify the media_type, to copy all manifest lists."""
        self.client.post(
            DOCKER_MANIFEST_COPY_PATH,
            {
                'source_repository': self.from_repo['pulp_href'],
                'destination_repository': self.to_repo['pulp_href'],
                'media_types': [MEDIA_TYPE.MANIFEST_LIST]
            }
        )
        latest_to_repo_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        to_repo_content = self.client.get(latest_to_repo_href)['content_summary']['present']
        self.assertFalse('docker.tag' in to_repo_content)
        # Fixture has 4 manifest lists, which combined reference 5 manifests
        self.assertEqual(to_repo_content['docker.manifest']['count'], 9)
        # each manifest (non-list) has 2 blobs
        self.assertEqual(to_repo_content['docker.blob']['count'], 10)

    def test_copy_all_manifests_by_media_type(self):
        """Specify the media_type, to copy all manifest lists."""
        self.client.post(
            DOCKER_MANIFEST_COPY_PATH,
            {
                'source_repository': self.from_repo['pulp_href'],
                'destination_repository': self.to_repo['pulp_href'],
                'media_types': [MEDIA_TYPE.MANIFEST_V1, MEDIA_TYPE.MANIFEST_V2]
            }
        )
        latest_to_repo_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        to_repo_content = self.client.get(latest_to_repo_href)['content_summary']['present']
        self.assertFalse('docker.tag' in to_repo_content)
        # Fixture has 5 manifests that aren't manifest lists
        self.assertEqual(to_repo_content['docker.manifest']['count'], 5)
        # each manifest (non-list) has 2 blobs
        self.assertEqual(to_repo_content['docker.blob']['count'], 10)

    def test_fail_to_copy_invalid_manifest_media_type(self):
        """Specify the media_type, to copy all manifest lists."""
        with self.assertRaises(HTTPError) as context:
            self.client.post(
                DOCKER_MANIFEST_COPY_PATH,
                {
                    'source_repository': self.from_repo['pulp_href'],
                    'destination_repository': self.to_repo['pulp_href'],
                    'media_types': ['wrongwrongwrong']
                }
            )
        self.assertEqual(context.exception.response.status_code, 400)

    def test_copy_by_digest_with_incorrect_media_type(self):
        """Ensure invalid media type will raise a 400."""
        ml_i_href = self.client.get("{unit_path}?{filters}".format(
            unit_path=DOCKER_TAG_PATH,
            filters="name=ml_i&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['tagged_manifest']
        ml_i_digest = self.client.get(ml_i_href)['digest']
        self.client.post(
            DOCKER_MANIFEST_COPY_PATH,
            {
                'source_repository': self.from_repo['pulp_href'],
                'destination_repository': self.to_repo['pulp_href'],
                'digests': [ml_i_digest],
                'media_types': [MEDIA_TYPE.MANIFEST_V2]
            }
        )
        latest_to_repo_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        to_repo_content = self.client.get(latest_to_repo_href)['content_summary']['present']
        # No content added
        for docker_type in ['docker.tag', 'docker.manifest', 'docker.blob']:
            self.assertFalse(docker_type in to_repo_content, msg=docker_type)

    def test_copy_multiple_manifests_by_digest(self):
        """Specify digests to copy."""
        ml_i_href = self.client.get("{unit_path}?{filters}".format(
            unit_path=DOCKER_TAG_PATH,
            filters="name=ml_i&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['tagged_manifest']
        ml_i_digest = self.client.get(ml_i_href)['digest']
        ml_ii_href = self.client.get("{unit_path}?{filters}".format(
            unit_path=DOCKER_TAG_PATH,
            filters="name=ml_ii&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['tagged_manifest']
        ml_ii_digest = self.client.get(ml_ii_href)['digest']
        self.client.post(
            DOCKER_MANIFEST_COPY_PATH,
            {
                'source_repository': self.from_repo['pulp_href'],
                'destination_repository': self.to_repo['pulp_href'],
                'digests': [ml_i_digest, ml_ii_digest]
            }
        )
        latest_to_repo_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        to_repo_content = self.client.get(latest_to_repo_href)['content_summary']['present']
        self.assertFalse('docker.tag' in to_repo_content)
        # each manifest list is a manifest and references 2 other manifests
        self.assertEqual(to_repo_content['docker.manifest']['count'], 6)
        # each referenced manifest has 2 blobs
        self.assertEqual(to_repo_content['docker.blob']['count'], 8)

    def test_copy_manifests_by_digest_empty_list(self):
        """Passing an empty list copies no manifests."""
        self.client.post(
            DOCKER_MANIFEST_COPY_PATH,
            {
                'source_repository': self.from_repo['pulp_href'],
                'destination_repository': self.to_repo['pulp_href'],
                'digests': []
            }
        )
        latest_to_repo_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        # A new version was created
        self.assertNotEqual(latest_to_repo_href, self.to_repo['latest_version_href'])

        to_repo_content = self.client.get(latest_to_repo_href)['content_summary']['present']
        # No content added
        for docker_type in ['docker.tag', 'docker.manifest', 'docker.blob']:
            self.assertFalse(docker_type in to_repo_content)


class TestTagCopy(unittest.TestCase):
    """Test recursive copy of tags content to a repository."""

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
        """Ensure source_repository or source_repository_version is required."""
        with self.assertRaises(HTTPError):
            self.client.post(DOCKER_RECURSIVE_ADD_PATH)

        with self.assertRaises(HTTPError):
            self.client.post(
                DOCKER_TAG_COPY_PATH,
                {'source_repository': self.from_repo['pulp_href']}
            )

        with self.assertRaises(HTTPError):
            self.client.post(
                DOCKER_TAG_COPY_PATH,
                {'source_repository_version': self.from_repo['latest_version_href']}
            )

        with self.assertRaises(HTTPError):
            self.client.post(
                DOCKER_TAG_COPY_PATH,
                {'destination_repository': self.to_repo['pulp_href']}
            )

    def test_empty_source_repository(self):
        """Ensure exception is raised when source_repository does not have latest version."""
        with self.assertRaises(HTTPError):
            self.client.post(
                DOCKER_TAG_COPY_PATH,
                {
                    # to_repo has no versions, use it as source
                    'source_repository': self.to_repo['pulp_href'],
                    'destination_repository': self.from_repo['pulp_href'],
                }
            )

    def test_source_repository_and_source_version(self):
        """Passing both source_repository_version and source_repository returns a 400."""
        with self.assertRaises(HTTPError) as context:
            self.client.post(
                DOCKER_TAG_COPY_PATH,
                {
                    'source_repository': self.from_repo['pulp_href'],
                    'source_repository_version': self.from_repo['latest_version_href'],
                    'destination_repository': self.to_repo['pulp_href']
                }
            )
        self.assertEqual(context.exception.response.status_code, 400)

    def test_copy_all_tags(self):
        """Passing only source and destination repositories copies all tags."""
        self.client.post(
            DOCKER_TAG_COPY_PATH,
            {
                'source_repository': self.from_repo['pulp_href'],
                'destination_repository': self.to_repo['pulp_href']
            }
        )
        latest_to_repo_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest_from_repo_href = self.client.get(self.from_repo['pulp_href'])['latest_version_href']
        to_repo_content = self.client.get(latest_to_repo_href)['content_summary']['present']
        from_repo_content = self.client.get(latest_from_repo_href)['content_summary']['present']
        for docker_type in ['docker.tag', 'docker.manifest', 'docker.blob']:
            self.assertEqual(
                to_repo_content[docker_type]['count'],
                from_repo_content[docker_type]['count'],
                msg=docker_type,
            )

    def test_copy_all_tags_from_version(self):
        """Passing only source version and destination repositories copies all tags."""
        latest_from_repo_href = self.client.get(self.from_repo['pulp_href'])['latest_version_href']
        self.client.post(
            DOCKER_TAG_COPY_PATH,
            {
                'source_repository_version': latest_from_repo_href,
                'destination_repository': self.to_repo['pulp_href']
            }
        )
        latest_to_repo_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        to_repo_content = self.client.get(latest_to_repo_href)['content_summary']['present']
        from_repo_content = self.client.get(latest_from_repo_href)['content_summary']['present']
        for docker_type in ['docker.tag', 'docker.manifest', 'docker.blob']:
            self.assertEqual(
                to_repo_content[docker_type]['count'],
                from_repo_content[docker_type]['count'],
                msg=docker_type,
            )

    def test_copy_tags_by_name(self):
        """Copy tags in destination repo that match name."""
        self.client.post(
            DOCKER_TAG_COPY_PATH,
            {
                'source_repository': self.from_repo['pulp_href'],
                'destination_repository': self.to_repo['pulp_href'],
                'names': ['ml_i', 'manifest_c']
            }
        )
        latest_to_repo_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        to_repo_content = self.client.get(latest_to_repo_href)['content_summary']['present']
        self.assertEqual(to_repo_content['docker.tag']['count'], 2)
        # ml_i has 1 manifest list, 2 manifests, manifest_c has 1 manifest
        self.assertEqual(to_repo_content['docker.manifest']['count'], 4)
        # each manifest (not manifest list) has 2 blobs
        self.assertEqual(to_repo_content['docker.blob']['count'], 6)

    def test_copy_tags_by_name_empty_list(self):
        """Passing an empty list of names copies nothing."""
        self.client.post(
            DOCKER_TAG_COPY_PATH,
            {
                'source_repository': self.from_repo['pulp_href'],
                'destination_repository': self.to_repo['pulp_href'],
                'names': []
            }
        )
        latest_to_repo_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        # A new version was created
        self.assertNotEqual(latest_to_repo_href, self.to_repo['latest_version_href'])

        to_repo_content = self.client.get(latest_to_repo_href)['content_summary']['present']
        # No content added
        for docker_type in ['docker.tag', 'docker.manifest', 'docker.blob']:
            self.assertFalse(docker_type in to_repo_content)

    def test_copy_tags_with_conflicting_names(self):
        """If tag names are already present in a repository, the conflicting tags are removed."""
        self.client.post(
            DOCKER_TAG_COPY_PATH,
            {
                'source_repository': self.from_repo['pulp_href'],
                'destination_repository': self.to_repo['pulp_href']
            }
        )
        # Same call
        self.client.post(
            DOCKER_TAG_COPY_PATH,
            {
                'source_repository': self.from_repo['pulp_href'],
                'destination_repository': self.to_repo['pulp_href']
            }
        )
        latest_to_repo_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest_from_repo_href = self.client.get(self.from_repo['pulp_href'])['latest_version_href']
        to_repo_content = self.client.get(latest_to_repo_href)['content_summary']
        from_repo_content = self.client.get(latest_from_repo_href)['content_summary']
        for docker_type in ['docker.tag', 'docker.manifest', 'docker.blob']:
            self.assertEqual(
                to_repo_content['present'][docker_type]['count'],
                from_repo_content['present'][docker_type]['count']
            )

        self.assertEqual(
            to_repo_content['added']['docker.tag']['count'],
            from_repo_content['present']['docker.tag']['count']
        )
        self.assertEqual(
            to_repo_content['removed']['docker.tag']['count'],
            from_repo_content['present']['docker.tag']['count']
        )


class TestRecursiveAdd(unittest.TestCase):
    """Test recursively adding docker content to a repository."""

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
        with self.assertRaises(HTTPError):
            self.client.post(DOCKER_RECURSIVE_ADD_PATH)

    def test_repository_only(self):
        """Passing only a repository creates a new version."""
        self.client.post(DOCKER_RECURSIVE_ADD_PATH, {'repository': self.to_repo['pulp_href']})
        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        self.assertNotEqual(latest_version_href, self.to_repo['latest_version_href'])

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

        # No tags added
        self.assertFalse('docker.manifest-tag' in latest['content_summary']['added'])

        # manifest a has 2 blobs
        self.assertEqual(latest['content_summary']['added']['docker.manifest']['count'], 1)
        self.assertEqual(latest['content_summary']['added']['docker.blob']['count'], 2)

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

        # No tags added
        self.assertFalse('docker.tag' in latest['content_summary']['added'])
        # 1 manifest list 2 manifests
        self.assertEqual(latest['content_summary']['added']['docker.manifest']['count'], 3)

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
        self.assertEqual(latest['content_summary']['added']['docker.tag']['count'], 1)
        # 1 manifest list 2 manifests
        self.assertEqual(latest['content_summary']['added']['docker.manifest']['count'], 3)
        self.assertEqual(latest['content_summary']['added']['docker.blob']['count'], 4)

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

        self.assertEqual(latest['content_summary']['added']['docker.tag']['count'], 1)
        self.assertEqual(latest['content_summary']['added']['docker.manifest']['count'], 1)
        self.assertEqual(latest['content_summary']['added']['docker.blob']['count'], 2)

    def test_tag_replacement(self):
        """Add a tagged manifest to a repo with a tag of that name already in place."""
        manifest_a_tag = self.client.get("{unit_path}?{filters}".format(
            unit_path=DOCKER_TAG_PATH,
            filters="name=manifest_a&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['pulp_href']

        # Add manifest_b to the repo
        manifest_b = self.client.get("{unit_path}?{filters}".format(
            unit_path=DOCKER_TAG_PATH,
            filters="name=manifest_b&{v_filter}".format(v_filter=self.latest_from_version),
        ))['results'][0]['tagged_manifest']
        manifest_b_digest = self.client.get(manifest_b)['digest']
        self.client.post(
            DOCKER_RECURSIVE_ADD_PATH,
            {'repository': self.to_repo['pulp_href'], 'content_units': [manifest_b]})
        # Tag manifest_b as `manifest_a`
        params = {
            'tag': "manifest_a",
            'repository': self.to_repo['pulp_href'],
            'digest': manifest_b_digest
        }
        self.client.post(DOCKER_TAGGING_PATH, params)

        # Now add original manifest_a tag to the repo, which should remove the
        # new manifest_a tag, but leave the tagged manifest (manifest_b)
        self.client.post(
            DOCKER_RECURSIVE_ADD_PATH,
            {'repository': self.to_repo['pulp_href'], 'content_units': [manifest_a_tag]})

        latest_version_href = self.client.get(self.to_repo['pulp_href'])['latest_version_href']
        latest = self.client.get(latest_version_href)
        self.assertEqual(latest['content_summary']['added']['docker.tag']['count'], 1)
        self.assertEqual(latest['content_summary']['removed']['docker.tag']['count'], 1)
        self.assertFalse('docker.manifest' in latest['content_summary']['removed'])
        self.assertFalse('docker.blob' in latest['content_summary']['removed'])

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

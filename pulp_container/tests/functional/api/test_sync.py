# coding=utf-8
"""Tests that sync container plugin repositories."""
import unittest

from pulp_smash import api, cli, config, exceptions
from pulp_smash.pulp3.constants import MEDIA_PATH
from pulp_smash.pulp3.utils import delete_orphans, gen_repo, sync

from pulp_container.tests.functional.constants import (
    CONTAINER_TAG_PATH,
    CONTAINER_REMOTE_PATH,
    CONTAINER_REPO_PATH,
    DOCKERHUB_PULP_FIXTURE_1,
)
from pulp_container.tests.functional.utils import gen_container_remote
from pulp_container.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class BasicSyncTestCase(unittest.TestCase):
    """Sync repositories with the container plugin."""

    maxDiff = None

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)

    def test_sync(self):
        """Sync repositories with the container plugin.

        In order to sync a repository a remote has to be associated within
        this repository. When a repository is created this version field is set
        as None. After a sync the repository version is updated.

        Do the following:

        1. Create a repository, and a remote.
        2. Assert that repository version is None.
        3. Sync the remote.
        4. Assert that repository version is not None.
        5. Sync the remote one more time.
        6. Assert that repository version is the same from the previous one.
        """
        repo = self.client.post(CONTAINER_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['pulp_href'])

        remote = self.client.post(CONTAINER_REMOTE_PATH, gen_container_remote())
        self.addCleanup(self.client.delete, remote['pulp_href'])

        # Sync the repository.
        self.assertIsNone(repo['latest_version_href'])
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['pulp_href'])
        self.assertIsNotNone(repo['latest_version_href'])

        # Sync the repository again.
        latest_version_href = repo['latest_version_href']
        sync(self.cfg, remote, repo)
        repo = self.client.get(repo['pulp_href'])
        self.assertEqual(latest_version_href, repo['latest_version_href'])

    def test_file_decriptors(self):
        """Test whether file descriptors are closed properly.

        This test targets the following issue:
        `Pulp #4073 <https://pulp.plan.io/issues/4073>`_

        Do the following:
        1. Check if 'lsof' is installed. If it is not, skip this test.
        2. Create and sync a repo.
        3. Run the 'lsof' command to verify that files in the
           path ``/var/lib/pulp/`` are closed after the sync.
        4. Assert that issued command returns `0` opened files.
        """
        cli_client = cli.Client(self.cfg, cli.echo_handler)

        # check if 'lsof' is available
        if cli_client.run(('which', 'lsof')).returncode != 0:
            raise unittest.SkipTest('lsof package is not present')

        repo = self.client.post(CONTAINER_REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, repo['pulp_href'])

        remote = self.client.post(CONTAINER_REMOTE_PATH, gen_container_remote())
        self.addCleanup(self.client.delete, remote['pulp_href'])

        sync(self.cfg, remote, repo)

        cmd = 'lsof -t +D {}'.format(MEDIA_PATH).split()
        response = cli_client.run(cmd).stdout
        self.assertEqual(len(response), 0, response)


class SyncInvalidURLTestCase(unittest.TestCase):
    """Sync a repository with an invalid url on the Remote."""

    def test_all(self):
        """
        Sync a repository using a Remote url that does not exist.

        Test that we get a task failure.

        """
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)

        repo = client.post(CONTAINER_REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo['pulp_href'])

        remote = client.post(
            CONTAINER_REMOTE_PATH,
            gen_container_remote(url="http://i-am-an-invalid-url.com/invalid/")
        )
        self.addCleanup(client.delete, remote['pulp_href'])

        with self.assertRaises(exceptions.TaskReportError):
            sync(cfg, remote, repo)


class TestRepeatedSync(unittest.TestCase):
    """Test behavior when a sync is repeated."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)
        cls.from_repo = cls.client.post(CONTAINER_REPO_PATH, gen_repo())
        remote_data = gen_container_remote(upstream_name=DOCKERHUB_PULP_FIXTURE_1)
        cls.remote = cls.client.post(CONTAINER_REMOTE_PATH, remote_data)
        delete_orphans(cls.cfg)

    @classmethod
    def tearDownClass(cls):
        """Delete things made in setUpClass. addCleanup feature does not work with setupClass."""
        cls.client.delete(cls.from_repo['pulp_href'])
        cls.client.delete(cls.remote['pulp_href'])
        delete_orphans(cls.cfg)

    def test_sync_idempotency(self):
        """Ensure that sync does not create orphan tags https://pulp.plan.io/issues/5252 ."""
        sync(self.cfg, self.remote, self.from_repo)
        first_sync_tags_named_a = self.client.get("{unit_path}?{filters}".format(
            unit_path=CONTAINER_TAG_PATH,
            filters="name=manifest_a",
        ))
        sync(self.cfg, self.remote, self.from_repo)
        second_sync_tags_named_a = self.client.get("{unit_path}?{filters}".format(
            unit_path=CONTAINER_TAG_PATH,
            filters="name=manifest_a",
        ))
        self.assertEqual(first_sync_tags_named_a['count'], 1)
        self.assertEqual(second_sync_tags_named_a['count'], 1)

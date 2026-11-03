import asyncio
import hashlib
import tempfile
import threading
from unittest.mock import patch
from uuid import uuid4

from aiohttp.test_utils import make_mocked_request
from django.db import connection
from django.test import TransactionTestCase

from pulpcore.plugin.content import PathNotResolved
from pulpcore.plugin.models import Artifact, ContentArtifact

from pulp_container.app.cache import RegistryContentCache
from pulp_container.app.models import Blob, ContainerDistribution, ContainerRepository
from pulp_container.app.registry import Registry
from pulp_container.constants import EMPTY_BLOB


class TestPendingBlobDuringVersionCommit(TransactionTestCase):
    """
    The content app serves a pull-through blob while a task commits the version that adds it.

    The blob starts in the repository's pending_blobs, as the registry API leaves it before
    redirecting a client to the content app. The task runs in another thread, on its own database
    connection, as a worker would. A TransactionTestCase lets each side see the other's commits.
    """

    # A TransactionTestCase empties the database after each test, including the rows migrations
    # create (such as the default domain). This restores them for the next test.
    serialized_rollback = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # One event loop for every request, as the content app has. With CACHE_ENABLED, the
        # cache around get_by_digest holds an async Redis client that stays bound to the loop it
        # first ran in.
        cls.event_loop = asyncio.Runner()

    @classmethod
    def tearDownClass(cls):
        # Close the Redis client's connections inside the loop they belong to, so nothing that
        # runs later finds them bound to a closed loop. Every content cache shares the one client;
        # it is None when the cache is disabled.
        redis = RegistryContentCache().redis
        if redis is not None:
            cls.event_loop.run(redis.connection_pool.disconnect())
        cls.event_loop.close()
        super().tearDownClass()

    def setUp(self):
        # A blob with a stored artifact. The registry finds a blob's ContentArtifact by
        # relative_path, which is the digest.
        data = uuid4().bytes
        self.digest = "sha256:" + hashlib.sha256(data).hexdigest()
        with tempfile.NamedTemporaryFile() as f:
            f.write(data)
            f.flush()
            artifact = Artifact.init_and_validate(f.name)
            artifact.save()
        self.blob = Blob.objects.create(digest=self.digest)
        ContentArtifact.objects.create(
            artifact=artifact, content=self.blob, relative_path=self.digest
        )

        # The repository has the blob only in pending_blobs, not yet in any version: the state
        # the registry API leaves on a cold pull. The distribution serves the repository's latest
        # version.
        self.repository = ContainerRepository.objects.create(name=str(uuid4()))
        self.repository.pending_blobs.add(self.blob)
        self.distribution = ContainerDistribution.objects.create(
            name=self.repository.name,
            base_path=self.repository.name,
            repository=self.repository,
        )

    def commit_version(self):
        """
        Commit a new version adding the blob, as the pull-through task does.

        Runs in its own thread, so it uses its own database connection; that connection is
        closed on the way out.
        """
        try:
            with self.repository.new_version() as version:
                version.add_content(Blob.objects.filter(pk=self.blob.pk))
        finally:
            connection.close()

    def get_blob(self):
        """
        Call Registry.get_by_digest for the blob, as the content app would.

        Returns the response; a 404 raises PathNotResolved, which fails a test that does not
        expect it.
        """

        # A real aiohttp request, because with CACHE_ENABLED the cache around get_by_digest looks
        # for one among the handler's arguments. match_info is what the content app's route
        # captures: the digest without its "sha256:" prefix. The request is made inside the event
        # loop that handles it.
        async def request_blob():
            base_path = self.distribution.base_path
            request = make_mocked_request(
                "GET",
                f"/pulp/container/{base_path}/blobs/{self.digest}",
                match_info={"path": base_path, "digest": self.digest[7:]},
            )
            return await Registry().get_by_digest(request)

        return self.event_loop.run(request_blob())

    def test_blob_served_while_version_commits(self):
        """The task is paused after finalize_new_version, before the version is complete."""
        # Wrap finalize_new_version so the task stops right after it and waits to be resumed.
        # The 5 second timeouts make a broken test fail instead of hanging.
        paused, resume = threading.Event(), threading.Event()
        finalize = ContainerRepository.finalize_new_version

        def finalize_then_pause(repository, new_version):
            finalize(repository, new_version)
            paused.set()
            resume.wait(5)

        with patch.object(
            ContainerRepository,
            "finalize_new_version",
            autospec=True,
            side_effect=finalize_then_pause,
        ):
            # Start the task and wait until it is paused, between finalizing the version and
            # committing it as complete. Request the blob in that window, then let the task
            # finish whatever the request returned.
            task = threading.Thread(target=self.commit_version)
            task.start()
            self.assertTrue(paused.wait(5))
            try:
                self.get_blob()
            finally:
                resume.set()
                task.join()

        # Once the version is complete the blob is no longer pending.
        self.assertFalse(self.repository.pending_blobs.exists())

    def test_blob_served_when_version_commits_between_lookups(self):
        """The version commits after the content app has read the repository version."""
        # Wrap get_repository_version so that, once get_by_digest has read the version, a task
        # commits a new version adding the blob, and finishes, before get_by_digest looks the
        # blob up.
        get_repository_version = ContainerDistribution.get_repository_version

        def read_then_commit(distribution):
            repository_version = get_repository_version(distribution)
            task = threading.Thread(target=self.commit_version)
            task.start()
            task.join()
            return repository_version

        with patch.object(
            ContainerDistribution,
            "get_repository_version",
            autospec=True,
            side_effect=read_then_commit,
        ):
            self.get_blob()

    def test_missing_blob_not_found(self):
        """A digest that is neither pending nor in the version is still a 404."""
        self.digest = "sha256:" + "0" * 64
        with self.assertRaises(PathNotResolved):
            self.get_blob()

    def test_empty_blob_served(self):
        """The empty blob is served without a ContentArtifact when a version is served."""
        self.digest = EMPTY_BLOB
        response = self.get_blob()
        self.assertEqual(response.headers["Docker-Content-Digest"], EMPTY_BLOB)

    def test_no_repository_version_not_found(self):
        """With no repository version served, every blob is a 404, the empty blob included."""
        # A distribution with neither a repository nor a repository version serves no version.
        self.distribution.repository = None
        self.distribution.save()
        for digest in (EMPTY_BLOB, self.digest):
            with self.subTest(digest=digest):
                self.digest = digest
                with self.assertRaises(PathNotResolved):
                    self.get_blob()

from gettext import gettext as _
import logging

from pulpcore.plugin.models import Repository
from pulpcore.plugin.stages import (
    ArtifactDownloader,
    ArtifactSaver,
    ContentSaver,
    DeclarativeVersion,
    RemoteArtifactSaver,
    RemoveDuplicates,
    ResolveContentFutures,
    QueryExistingArtifacts,
    QueryExistingContents,
)

from .sync_stages import InterrelateContent, ContainerFirstStage
from pulp_container.app.models import ContainerRemote, Tag


log = logging.getLogger(__name__)


def synchronize(remote_pk, repository_pk):
    """
    Sync content from the remote repository.

    Create a new version of the repository that is synchronized with the remote.

    Args:
        remote_pk (str): The remote PK.
        repository_pk (str): The repository PK.

    Raises:
        ValueError: If the remote does not specify a URL to sync

    """
    remote = ContainerRemote.objects.get(pk=remote_pk)
    repository = Repository.objects.get(pk=repository_pk)
    if not remote.url:
        raise ValueError(_('A remote must have a url specified to synchronize.'))
    remove_duplicate_tags = [{'model': Tag, 'field_names': ['name']}]
    log.info(_('Synchronizing: repository={r} remote={p}').format(
        r=repository.name, p=remote.name))
    first_stage = ContainerFirstStage(remote)
    dv = ContainerDeclarativeVersion(first_stage,
                                     repository,
                                     remove_duplicates=remove_duplicate_tags)
    dv.create()


class ContainerDeclarativeVersion(DeclarativeVersion):
    """
    Subclassed Declarative version creates a custom pipeline for Container sync.
    """

    def pipeline_stages(self, new_version):
        """
        Build a list of stages feeding into the ContentUnitAssociation stage.

        This defines the "architecture" of the entire sync.

        Args:
            new_version (:class:`~pulpcore.plugin.models.RepositoryVersion`): The
                new repository version that is going to be built.

        Returns:
            list: List of :class:`~pulpcore.plugin.stages.Stage` instances

        """
        pipeline = [
            self.first_stage,
            QueryExistingArtifacts(),
            ArtifactDownloader(),
            ArtifactSaver(),
            QueryExistingContents(),
            ContentSaver(),
            RemoteArtifactSaver(),
            ResolveContentFutures(),
            InterrelateContent(),
        ]
        for dupe_query_dict in self.remove_duplicates:
            pipeline.append(RemoveDuplicates(new_version, **dupe_query_dict))

        return pipeline

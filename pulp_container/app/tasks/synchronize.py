from gettext import gettext as _
import logging

from pulpcore.plugin.stages import (
    ArtifactDownloader,
    ArtifactSaver,
    ContentSaver,
    DeclarativeVersion,
    RemoteArtifactSaver,
    ResolveContentFutures,
    QueryExistingArtifacts,
    QueryExistingContents,
)

from .sync_stages import InterrelateContent, ContainerFirstStage
from pulp_container.app.models import ContainerRemote, ContainerRepository


log = logging.getLogger(__name__)


def synchronize(remote_pk, repository_pk, mirror):
    """
    Sync content from the remote repository.

    Create a new version of the repository that is synchronized with the remote.

    Args:
        remote_pk (str): The remote PK.
        repository_pk (str): The repository PK.
        mirror (boolean): A boolean indicating enabled or disabled mirror mode.

    Raises:
        ValueError: If the remote does not specify a URL to sync

    """
    remote = ContainerRemote.objects.get(pk=remote_pk)
    repository = ContainerRepository.objects.get(pk=repository_pk)
    if not remote.url:
        raise ValueError(_("A remote must have a url specified to synchronize."))
    log.info(_("Synchronizing: repository={r} remote={p}").format(r=repository.name, p=remote.name))
    first_stage = ContainerFirstStage(remote)
    dv = ContainerDeclarativeVersion(first_stage, repository, mirror)
    return dv.create()


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

        return pipeline

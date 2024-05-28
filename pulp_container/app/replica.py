from pulpcore.plugin.replica import Replicator
from pulpcore.plugin.util import get_url

from pulp_glue.container.context import (
    PulpContainerDistributionContext,
    PulpContainerRepositoryContext,
)

from pulp_container.app.models import ContainerDistribution, ContainerRemote, ContainerRepository
from pulp_container.app.tasks import synchronize as container_synchronize


class ContainerReplicator(Replicator):
    distribution_ctx_cls = PulpContainerDistributionContext
    repository_ctx_cls = PulpContainerRepositoryContext
    remote_model_cls = ContainerRemote
    repository_model_cls = ContainerRepository
    distribution_model_cls = ContainerDistribution
    distribution_serializer_name = "ContainerDistributionSerializer"
    repository_serializer_name = "ContainerRepositorySerializer"
    remote_serializer_name = "ContainerRemoteSerializer"
    app_label = "container"
    sync_task = container_synchronize

    def sync_params(self, repository, remote):
        """Returns a dictionary where key is a parameter for the sync task."""
        return dict(
            remote_pk=str(remote.pk),
            repository_pk=str(repository.pk),
            signed_only=False,
            mirror=True,
        )

    def url(self, upstream_distribution):
        return self.pulp_ctx._api_kwargs["base_url"]

    def remote_extra_fields(self, upstream_distribution):
        upstream_name = upstream_distribution["registry_path"].split("/", 1)[1]
        return {"upstream_name": upstream_name}

    def distribution_data(self, repository, upstream_distribution):
        """
        Return the fields that need to be updated/cleared on distributions for idempotence.
        """
        return {
            "repository": get_url(repository),
            "base_path": upstream_distribution["base_path"],
            "private": upstream_distribution["private"],
            "description": upstream_distribution["description"],
        }


REPLICATION_ORDER = [ContainerReplicator]

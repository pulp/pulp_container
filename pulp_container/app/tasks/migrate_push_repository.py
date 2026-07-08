from django.db import transaction

from pulpcore.plugin.models import CreatedResource

from pulp_container.app.models import (
    ContainerDistribution,
    ContainerPushRepository,
    ContainerRepository,
)
from pulp_container.app.serializers import ContainerRepositorySerializer


def migrate_push_repository(push_repository_pk, copy_versions=False):
    """
    Convert a ContainerPushRepository into a ContainerRepository.

    Creates a new container repository with the same name and metadata, copies
    content from the push repository, reassociates any distributions, and deletes
    the original push repository.

    Args:
        push_repository_pk (str): The primary key for the push repository to migrate.
        copy_versions (bool): If True, copy the full repository version history. If False,
            only copy content from the latest repository version.
    """
    push_repository = ContainerPushRepository.objects.get(pk=push_repository_pk)

    original_name = push_repository.name
    temp_name = f"{original_name}__migrating__{push_repository.pk}"

    with transaction.atomic():
        push_repository.name = temp_name
        push_repository.save(update_fields=["name"])

        container_repository = ContainerRepository(
            name=original_name,
            pulp_domain=push_repository.pulp_domain,
            pulp_labels=push_repository.pulp_labels,
            description=push_repository.description,
            retain_repo_versions=push_repository.retain_repo_versions,
            retain_checkpoints=push_repository.retain_checkpoints,
            user_hidden=push_repository.user_hidden,
            manifest_signing_service=push_repository.manifest_signing_service,
        )
        container_repository.save()

        container_repository.pending_blobs.set(push_repository.pending_blobs.all())
        container_repository.pending_manifests.set(push_repository.pending_manifests.all())

        if copy_versions:
            for push_version in push_repository.versions.complete().order_by("number"):
                if push_version.number == 0 and not push_version.content.exists():
                    continue
                with container_repository.new_version() as new_version:
                    new_version.set_content(push_version.content.all())
        else:
            latest_version = push_repository.latest_version()
            if latest_version:
                with container_repository.new_version() as new_version:
                    new_version.set_content(latest_version.content.all())

        ContainerDistribution.objects.filter(repository=push_repository).update(
            repository=container_repository
        )

        push_repository.delete()

    CreatedResource(content_object=container_repository).save()

    return ContainerRepositorySerializer(
        instance=container_repository, context={"request": None}
    ).data

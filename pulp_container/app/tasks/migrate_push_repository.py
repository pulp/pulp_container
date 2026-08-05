from django.contrib.contenttypes.models import ContentType
from django.db import connection, transaction

from pulpcore.plugin.models import CreatedResource
from pulpcore.plugin.models.role import GroupRole, UserRole

from pulp_container.app.models import ContainerPushRepository, ContainerRepository
from pulp_container.app.serializers import ContainerRepositorySerializer


def migrate_push_repository(push_repository_pk):
    """
    Convert a ContainerPushRepository into a ContainerRepository in place.

    Swaps the multi-table-inheritance child row and updates `pulp_type` on the
    parent repository so the primary key is preserved. Repository versions,
    distributions, and other FKs to `core.Repository` remain valid.

    Args:
        push_repository_pk (str): The primary key for the push repository to migrate.
    """
    with transaction.atomic():
        with connection.cursor() as cursor:
            # First statement in the transaction: protect related reads/writes
            # (pending M2Ms, role GFKs) that are not covered by row locks alone.
            cursor.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")

        # FOR UPDATE on the MTI join locks both the push child row and the parent
        # core_repository row for the duration of this transaction.
        push_repository = ContainerPushRepository.objects.select_for_update().get(
            pk=push_repository_pk
        )
        # Sanity check only: pulp_type should still be container-push
        if push_repository.pulp_type != ContainerPushRepository.get_pulp_type():
            raise RuntimeError(
                f"Repository {push_repository_pk} has pulp_type "
                f"{push_repository.pulp_type!r}, expected a push repository."
            )
        if ContainerRepository.objects.filter(pk=push_repository_pk).exists():
            raise RuntimeError(
                f"Container repository child row already exists for {push_repository_pk}."
            )

        signing_service_id = push_repository.manifest_signing_service_id
        push_ct = ContentType.objects.get_for_model(ContainerPushRepository)
        container_ct = ContentType.objects.get_for_model(ContainerRepository)

        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE core_repository
                SET pulp_type = %s
                WHERE pulp_id = %s AND pulp_type = %s
                """,
                [
                    ContainerRepository.get_pulp_type(),
                    push_repository_pk,
                    ContainerPushRepository.get_pulp_type(),
                ],
            )
            if cursor.rowcount != 1:
                raise RuntimeError(
                    f"Failed to update pulp_type for repository {push_repository_pk}."
                )

            cursor.execute(
                """
                INSERT INTO container_containerrepository
                    (repository_ptr_id, manifest_signing_service_id)
                VALUES (%s, %s)
                """,
                [push_repository_pk, signing_service_id],
            )

            cursor.execute(
                """
                INSERT INTO container_containerrepository_pending_blobs
                    (containerrepository_id, blob_id)
                SELECT containerpushrepository_id, blob_id
                FROM container_containerpushrepository_pending_blobs
                WHERE containerpushrepository_id = %s
                """,
                [push_repository_pk],
            )
            cursor.execute(
                """
                INSERT INTO container_containerrepository_pending_manifests
                    (containerrepository_id, manifest_id)
                SELECT containerpushrepository_id, manifest_id
                FROM container_containerpushrepository_pending_manifests
                WHERE containerpushrepository_id = %s
                """,
                [push_repository_pk],
            )

            # Pending M2M FKs are ON DELETE NO ACTION at the DB level (not CASCADE),
            # so remove them explicitly before deleting the push child.
            cursor.execute(
                """
                DELETE FROM container_containerpushrepository_pending_blobs
                WHERE containerpushrepository_id = %s
                """,
                [push_repository_pk],
            )
            cursor.execute(
                """
                DELETE FROM container_containerpushrepository_pending_manifests
                WHERE containerpushrepository_id = %s
                """,
                [push_repository_pk],
            )
            cursor.execute(
                """
                DELETE FROM container_containerpushrepository
                WHERE repository_ptr_id = %s
                """,
                [push_repository_pk],
            )

        UserRole.objects.filter(content_type=push_ct, object_id=str(push_repository_pk)).update(
            content_type=container_ct
        )
        GroupRole.objects.filter(content_type=push_ct, object_id=str(push_repository_pk)).update(
            content_type=container_ct
        )

        container_repository = ContainerRepository.objects.get(pk=push_repository_pk)

    CreatedResource(content_object=container_repository).save()

    return ContainerRepositorySerializer(
        instance=container_repository, context={"request": None}
    ).data

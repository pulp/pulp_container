from pulpcore.plugin import PulpPluginAppConfig
from django.db import connection
from django.db.models.signals import post_migrate

update_sequences_to_bigint = """
ALTER TABLE container_blobmanifest ALTER COLUMN id TYPE bigint;
ALTER TABLE container_manifestlistmanifest ALTER COLUMN id TYPE bigint;
ALTER TABLE container_containerpushrepository_pending_blobs ALTER COLUMN id TYPE bigint;
ALTER TABLE container_containerpushrepository_pending_manifests ALTER COLUMN id TYPE bigint;
ALTER TABLE container_containerrepository_pending_manifests ALTER COLUMN id TYPE bigint;
ALTER TABLE container_containerrepository_pending_blobs ALTER COLUMN id TYPE bigint;
ALTER SEQUENCE container_blobmanifest_id_seq AS BIGINT;
ALTER SEQUENCE container_manifestlistmanifest_id_seq AS BIGINT;
ALTER SEQUENCE container_containerpushrepository_pending_blobs_id_seq AS BIGINT;
ALTER SEQUENCE container_containerpushrepository_pending_manifests_id_seq AS BIGINT;
ALTER SEQUENCE container_containerrepository_pending_blobs_id_seq AS BIGINT;
ALTER SEQUENCE container_containerrepository_pending_manifests_id_seq AS BIGINT;
"""


class PulpContainerPluginAppConfig(PulpPluginAppConfig):
    """Entry point for the container plugin."""

    name = "pulp_container.app"
    label = "container"
    version = "2.26.9.dev"
    python_package_name = "pulp-container"
    domain_compatible = True

    @staticmethod
    def update_sequences(sender, **kwargs):
        """Update database sequences to bigint type after migrations."""
        with connection.cursor() as cursor:
            cursor.execute(update_sequences_to_bigint)

    def ready(self):
        super().ready()
        from . import checks

        post_migrate.connect(PulpContainerPluginAppConfig.update_sequences, sender=self)

from django.db.models.signals import pre_delete

from pulpcore.plugin import PulpPluginAppConfig

from pulp_container.app.signals import delete_from_storage


class PulpContainerPluginAppConfig(PulpPluginAppConfig):
    """Entry point for the container plugin."""

    name = "pulp_container.app"
    label = "container"

    def ready(self):
        """
        Set up the action that will be triggered when the model is deleted via the CASCADE mode.
        """
        super().ready()

        BlobTemporaryUpload = self.get_model("BlobTemporaryUpload")  # noqa
        pre_delete.connect(delete_from_storage, sender=BlobTemporaryUpload)

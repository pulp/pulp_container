from pulpcore.plugin import PulpPluginAppConfig


class PulpContainerPluginAppConfig(PulpPluginAppConfig):
    """Entry point for the container plugin."""

    name = "pulp_container.app"
    label = "container"
    version = "2.19.2"
    python_package_name = "pulp-container"

    def ready(self):
        super().ready()
        self.register_registry_types()

    def register_registry_types(self):
        # circular import avoidance
        from pulp_container import constants
        from django.conf import settings

        for media_type, layer_types in settings.ADDITIONAL_OCI_ARTIFACT_TYPES.items():
            constants.register_well_known_types(media_type, layer_types)

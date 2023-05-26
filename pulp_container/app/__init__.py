from pulpcore.plugin import PulpPluginAppConfig


class PulpContainerPluginAppConfig(PulpPluginAppConfig):
    """Entry point for the container plugin."""

    name = "pulp_container.app"
    label = "container"
    version = "2.16.0.dev"
    python_package_name = "pulp-container"

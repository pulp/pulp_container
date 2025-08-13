from dynaconf import ValidationError


def post(settings):
    data = {"dynaconf_merge": True}
    enabled_plugins = settings.get("ENABLED_PLUGINS")
    if enabled_plugins and "pulp_file" not in enabled_plugins:
        raise ValidationError("pulp_file must be enabled to use pulp_container")
    return data

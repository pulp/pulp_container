from django.conf import settings
from django.core.checks import Error as CheckError, register


@register(deploy=True)
def container_settings_check(app_configs, **kwargs):
    errors = []

    # Other checks only apply if token auth is enabled
    if str(getattr(settings, "TOKEN_AUTH_DISABLED", False)).lower() == "true":
        return errors

    if getattr(settings, "TOKEN_SERVER", None) is None:
        errors.append(
            CheckError(
                "TOKEN_SERVER is a required setting that has to be configured when token"
                " authentification is enabled",
                id="pulp_container.E001",
            ),
        )
    if getattr(settings, "TOKEN_SIGNATURE_ALGORITHM", None) is None:
        errors.append(
            CheckError(
                "TOKEN_SIGNATURE_ALGORITHM is a required setting that has to be configured when"
                " token authentification is enabled",
                id="pulp_container.E001",
            )
        )
    if getattr(settings, "PUBLIC_KEY_PATH", None) is None:
        errors.append(
            CheckError(
                "PUBLIC_KEY_PATH is a required setting that has to be configured when token"
                " authentification is enabled",
                id="pulp_container.E001",
            )
        )
    if getattr(settings, "PRIVATE_KEY_PATH", None) is None:
        errors.append(
            CheckError(
                "PRIVATE_KEY_PATH is a required setting that has to be configured when token"
                " authentification is enabled",
                id="pulp_container.E001",
            )
        )

    return errors

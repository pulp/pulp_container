from copy import deepcopy
from django.conf import settings

DRF_ACCESS_POLICY = {
    "dynaconf_merge_unique": True,
    "reusable_conditions": ["pulp_container.app.global_access_conditions"],
}

REST_FRAMEWORK = deepcopy(settings.REST_FRAMEWORK)
REST_FRAMEWORK.update(
    {"EXCEPTION_HANDLER": "pulp_container.app.exceptions.unauthorized_exception_handler"}
)

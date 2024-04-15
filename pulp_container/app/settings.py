DRF_ACCESS_POLICY = {
    "dynaconf_merge_unique": True,
    "reusable_conditions": ["pulp_container.app.global_access_conditions"],
}

FLATPAK_INDEX = False

# The number of allowed threads to sign manifests in parallel
MAX_PARALLEL_SIGNING_TASKS = 10

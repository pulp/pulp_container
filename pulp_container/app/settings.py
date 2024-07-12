DRF_ACCESS_POLICY = {
    "dynaconf_merge_unique": True,
    "reusable_conditions": ["pulp_container.app.global_access_conditions"],
}

TOKEN_AUTH_DISABLED = False
FLATPAK_INDEX = False

# The number of allowed threads to sign manifests in parallel
MAX_PARALLEL_SIGNING_TASKS = 10

# Set max payload size for non-blob container artifacts (manifests, signatures, etc).
# This limit is also valid for docker manifests, but we will use the OCI_ prefix
# (instead of ARTIFACT_) to avoid confusion with pulpcore artifacts.
OCI_PAYLOAD_MAX_SIZE = 4_000_000

DRF_ACCESS_POLICY = {
    "dynaconf_merge_unique": True,
    "reusable_conditions": ["pulp_container.app.global_access_conditions"],
}

ADDITIONAL_OCI_ARTIFACT_TYPES = {
    "application/vnd.oci.image.config.v1+json": [
        # cosign signing and attestations
        "application/vnd.dev.cosign.simplesigning.v1+json",
        "application/vnd.dsse.envelope.v1+json",
        # cosign SBOMS spdx and cyclonedx
        "text/spdx",
        "text/spdx+xml",
        "text/spdx+json",
        "application/vnd.cyclonedx",
        "application/vnd.cyclonedx+xml",
        "application/vnd.cyclonedx+json",
        # syft SBOMS
        "application/vnd.syft+json",
        # cosign in-toto attestations
        "application/vnd.in-toto+json",
    ],
    # helm
    "application/vnd.cncf.helm.config.v1+json": [
        "application/tar+gzip",
        "application/vnd.cncf.helm.chart.content.v1.tar+gzip",
        "application/vnd.cncf.helm.chart.provenance.v1.prov",
    ],
    # source containers
    "application/vnd.oci.source.image.config.v1+json": [
        "application/vnd.oci.image.layer.v1.tar+gzip",
    ],
    # conftest policies
    "application/vnd.cncf.openpolicyagent.config.v1+json": [
        "application/vnd.cncf.openpolicyagent.policy.layer.v1+rego",
        "application/vnd.cncf.openpolicyagent.data.layer.v1+json",
        "application/vnd.cncf.openpolicyagent.manifest.layer.v1+json",
        "application/vnd.cncf.openpolicyagent.rego.layer.v1+rego",
    ],
    # singularity
    "application/vnd.sylabs.sif.config.v1+json": [
        "application/vnd.sylabs.sif.layer.v1.sif",
    ],
    # wasm
    "application/vnd.wasm.config.v1+json": [
        "application/vnd.wasm.content.layer.v1+wasm",
    ],
}

FLATPAK_INDEX = False

# The number of allowed threads to sign manifests in parallel
MAX_PARALLEL_SIGNING_TASKS = 10

from types import SimpleNamespace


MEDIA_TYPE = SimpleNamespace(
    MANIFEST_V1="application/vnd.docker.distribution.manifest.v1+json",
    MANIFEST_V1_SIGNED="application/vnd.docker.distribution.manifest.v1+prettyjws",
    MANIFEST_V2="application/vnd.docker.distribution.manifest.v2+json",
    MANIFEST_LIST="application/vnd.docker.distribution.manifest.list.v2+json",
    CONFIG_BLOB="application/vnd.docker.container.image.v1+json",
    REGULAR_BLOB="application/vnd.docker.image.rootfs.diff.tar.gzip",
    FOREIGN_BLOB="application/vnd.docker.image.rootfs.foreign.diff.tar.gzip",
    MANIFEST_OCI="application/vnd.oci.image.manifest.v1+json",
    INDEX_OCI="application/vnd.oci.image.index.v1+json",
    CONFIG_BLOB_OCI="application/vnd.oci.image.config.v1+json",
    REGULAR_BLOB_OCI_TAR="application/vnd.oci.image.layer.v1.tar",
    REGULAR_BLOB_OCI_TAR_GZIP="application/vnd.oci.image.layer.v1.tar+gzip",
    REGULAR_BLOB_OCI_TAR_ZSTD="application/vnd.oci.image.layer.v1.tar+zstd",
    FOREIGN_BLOB_OCI_TAR="application/vnd.oci.image.layer.nondistributable.v1.tar",
    FOREIGN_BLOB_OCI_TAR_GZIP="application/vnd.oci.image.layer.nondistributable.v1.tar+gzip",
    FOREIGN_BLOB_OCI_TAR_ZSTD="application/vnd.oci.image.layer.nondistributable.v1.tar+zstd",
    OCI_EMPTY_JSON="application/vnd.oci.empty.v1+json",
    CONFIG_BLOB_HELM="application/vnd.cncf.helm.config.v1+json",
    COSIGN_BLOB="application/vnd.dev.cosign.simplesigning.v1+json",
    COSIGN_ATTESTATION="application/vnd.dsse.envelope.v1+json",
    COSIGN_ATTESTATION_BUNDLE="application/vnd.dev.sigstore.bundle.v0.3+json",
)

V2_ACCEPT_HEADERS = {
    "Accept": ",".join(
        [
            MEDIA_TYPE.MANIFEST_V2,
            MEDIA_TYPE.MANIFEST_V1,
            MEDIA_TYPE.MANIFEST_V1_SIGNED,
            MEDIA_TYPE.MANIFEST_LIST,
            MEDIA_TYPE.INDEX_OCI,
            MEDIA_TYPE.MANIFEST_OCI,
        ]
    )
}

MANIFEST_MEDIA_TYPES = SimpleNamespace(
    IMAGE=[
        MEDIA_TYPE.MANIFEST_V1,
        MEDIA_TYPE.MANIFEST_V1_SIGNED,
        MEDIA_TYPE.MANIFEST_V2,
        MEDIA_TYPE.MANIFEST_OCI,
    ],
    LIST=[MEDIA_TYPE.MANIFEST_LIST, MEDIA_TYPE.INDEX_OCI],
)

OCI_BLOB_DISTRIBUTABLE_MEDIA_TYPE = [
    MEDIA_TYPE.REGULAR_BLOB_OCI_TAR,
    MEDIA_TYPE.REGULAR_BLOB_OCI_TAR_GZIP,
    MEDIA_TYPE.REGULAR_BLOB_OCI_TAR_ZSTD,
    MEDIA_TYPE.OCI_EMPTY_JSON,
]
OCI_BLOB_NON_DISTRIBUTABLE_MEDIA_TYPE = [
    MEDIA_TYPE.FOREIGN_BLOB_OCI_TAR,
    MEDIA_TYPE.FOREIGN_BLOB_OCI_TAR_GZIP,
    MEDIA_TYPE.FOREIGN_BLOB_OCI_TAR_ZSTD,
]
OCI_BLOB_MEDIA_TYPE = OCI_BLOB_DISTRIBUTABLE_MEDIA_TYPE + OCI_BLOB_NON_DISTRIBUTABLE_MEDIA_TYPE

EMPTY_BLOB = "sha256:a3ed95caeb02ffe68cdd9fd84406680ae93d633cb16422d00e8a7c22955b46d4"
EMPTY_JSON = "sha256:44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
BLOB_CONTENT_TYPE = "application/octet-stream"
SIGNATURE_TYPE = SimpleNamespace(
    ATOMIC_FULL="atomic container signature",  # full version is present in the signed document
    ATOMIC_SHORT="atomic",  # short version is used in the JSON produced by API extension
)
SIGNATURE_SOURCE = SimpleNamespace(SIGSTORE="sigstore", API_EXTENSION="API extension")
SIGNATURE_HEADER = "X-Registry-Supports-Signatures"

MEGABYTE = 1_000_000
SIGNATURE_PAYLOAD_MAX_SIZE = 4 * MEGABYTE

SIGNATURE_API_EXTENSION_VERSION = 2

MANIFEST_TYPE = SimpleNamespace(
    ARTIFACT="artifact",
    BOOTABLE="bootable",
    COSIGN_ATTESTATION="cosign_attestation",
    COSIGN_ATTESTATION_BUNDLE="cosign_attestation_bundle",
    COSIGN_SBOM="cosign_sbom",
    COSIGN_SIGNATURE="cosign_signature",
    FLATPAK="flatpak",
    HELM="helm",
    IMAGE="image",
    INDEX="index",
    UNKNOWN="unknown",
)

# COSIGN SPEC
# note: SBOM attachments are deprecated and support will be removed in a Cosign release soon
COSIGN_SBOM_FORMATS = ["application/vnd.cyclonedx", "text/spdx", "application/vnd.syft+json"]
COSIGN_SBOM_FORMATS_SUFFIXES = ["xml", "json"]
COSIGN_SBOM_FORMATS_WITH_SUFFIXES = [
    f"{sbom_formats}+{sbom_suffixes}"
    for sbom_formats in COSIGN_SBOM_FORMATS
    if sbom_formats != "application/vnd.syft+json"  # syft is a JSON only format
    for sbom_suffixes in COSIGN_SBOM_FORMATS_SUFFIXES
]

MEDIA_TYPE.COSIGN_SBOM = COSIGN_SBOM_FORMATS + COSIGN_SBOM_FORMATS_WITH_SUFFIXES
COSIGN_MEDIA_TYPES = [
    *MEDIA_TYPE.COSIGN_SBOM,
    MEDIA_TYPE.COSIGN_BLOB,
    MEDIA_TYPE.COSIGN_ATTESTATION,
    MEDIA_TYPE.COSIGN_ATTESTATION_BUNDLE,
]

COSIGN_MEDIA_TYPES_MANIFEST_TYPE_MAPPING = {
    MEDIA_TYPE.COSIGN_BLOB: MANIFEST_TYPE.COSIGN_SIGNATURE,
    MEDIA_TYPE.COSIGN_ATTESTATION: MANIFEST_TYPE.COSIGN_ATTESTATION,
    MEDIA_TYPE.COSIGN_ATTESTATION_BUNDLE: MANIFEST_TYPE.COSIGN_ATTESTATION_BUNDLE,
}

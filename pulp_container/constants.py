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
)

MANIFEST_MEDIA_TYPES = SimpleNamespace(
    IMAGE=[
        MEDIA_TYPE.MANIFEST_V1,
        MEDIA_TYPE.MANIFEST_V1_SIGNED,
        MEDIA_TYPE.MANIFEST_V2,
        MEDIA_TYPE.MANIFEST_OCI,
    ],
    LIST=[MEDIA_TYPE.MANIFEST_LIST, MEDIA_TYPE.INDEX_OCI],
)

EMPTY_BLOB = "sha256:a3ed95caeb02ffe68cdd9fd84406680ae93d633cb16422d00e8a7c22955b46d4"
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

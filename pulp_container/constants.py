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
    REGULAR_BLOB_OCI="application/vnd.oci.image.layer.v1.tar+gzip",
    FOREIGN_BLOB_OCI="application/vnd.oci.image.layer.nondistributable.v1.tar+gzip",
)
EMPTY_BLOB = "sha256:a3ed95caeb02ffe68cdd9fd84406680ae93d633cb16422d00e8a7c22955b46d4"
BLOB_CONTENT_TYPE = "application/octet-stream"

MANIFEST_MEDIA_TYPES = SimpleNamespace(
    IMAGE=[
        MEDIA_TYPE.MANIFEST_V1,
        MEDIA_TYPE.MANIFEST_V1_SIGNED,
        MEDIA_TYPE.MANIFEST_V2,
        MEDIA_TYPE.MANIFEST_OCI,
    ],
    LIST=[MEDIA_TYPE.MANIFEST_LIST, MEDIA_TYPE.INDEX_OCI],
)

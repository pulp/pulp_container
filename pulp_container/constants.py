from types import SimpleNamespace


MEDIA_TYPE = SimpleNamespace(
    MANIFEST_V1='application/vnd.docker.distribution.manifest.v1+json',
    MANIFEST_V1_SIGNED='application/vnd.docker.distribution.manifest.v1+prettyjws',
    MANIFEST_V2='application/vnd.docker.distribution.manifest.v2+json',
    MANIFEST_LIST='application/vnd.docker.distribution.manifest.list.v2+json',
    CONFIG_BLOB='application/vnd.docker.container.image.v1+json',
    REGULAR_BLOB='application/vnd.docker.image.rootfs.diff.tar.gzip',
    FOREIGN_BLOB='application/vnd.docker.image.rootfs.foreign.diff.tar.gzip',
)

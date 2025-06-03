# Push Images

Users can push images (manifests and manifest lists) to repositories hosted by the Container
Registry. It is possible to push images that container foreign (non-distributable) layers. Only the
users who are logged in to the registry are allowed to perform push operation. Find below a complete
example of pushing a tagged image.

!!! note

    Having disabled the token authentication, only users with superuser privileges (i.e.,
    administrators) are allowed to push content to the registry.

The registry supports cross repository blob mounting. When uploading blobs that already exist in
the registry as a part of a different repository, the content is not being uploaded but rather
referenced from another repository to reduce network traffic.

```
podman tag d21d863f69b5 localhost:24817/test/this:mytag1.8
podman login -u user -p password localhost:24817
podman push d21d863f69b5 localhost:24817/test/this:mytag1.8
```

```
http GET $BASE_ADDR/v2/test/this/tags/list
```

```
HTTP/1.1 200 OK
Allow: GET, HEAD, OPTIONS
Connection: close
Content-Length: 40
Content-Type: application/json
Date: Wed, 03 Jun 2020 18:25:46 GMT
Docker-Distribution-API-Version: registry/2.0
Server: gunicorn/20.0.4
Vary: Accept
X-Frame-Options: SAMEORIGIN

{
    "name": "test/this",
    "tags": [
        "mytag1.8"
    ]
}
```

!!! note

    Content is pushed to a push repository type. A push repository does not support mirroring of the
    remote content via the Pulp API. Trying to push content with the same name as an existing
    "regular" repository will fail.

!!! note

    Rollback to the previous repository versions is not possible with a push repository. Its latest version will always be served.

!!! warning

    Image that has been pulled from a registry and then subsequently pushed to another registy can lead to the blobs digest change.
    Most image layers on registries are compressed. Pull operation decompresses them to get an uncompressed stream, and extracts it
    to create the local filesystem. Push creates an uncompressed tarball from the local filesystem and recompresses it during upload.
    The recompression is not at all guaranteed to be reproducible, it is client implementation dependent — push with different
    compression implementation than the original author used is more likely to result in a different blob digest.

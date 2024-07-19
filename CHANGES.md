# Changelog

[//]: # (You should *NOT* be adding new change log entries to this file, this)
[//]: # (file is managed by towncrier. You *may* edit previous change logs to)
[//]: # (fix problems like typo corrections or such.)
[//]: # (To add a new change log entry, please see the contributing docs.)
[//]: # (WARNING: Don't drop the towncrier directive!)

[//]: # (towncrier release notes start)

## 2.21.0 (2024-07-19) {: #2.21.0 }


#### Features {: #2.21.0-feature }

- Added support for filtering remote repositories in pull-through caching using `includes` and
  `excludes` fields. These fields can be set on pull-through caching remote objects.
  [#459](https://github.com/pulp/pulp_container/issues/459)
- Added support for the Replication feature. The replication process allows a Pulp instance to
  replicate container repositories from an upstream Pulp, creating the required remotes,
  repositories (those will always be read-only), and distributions.
  [#1648](https://github.com/pulp/pulp_container/issues/1648)

#### Bugfixes {: #2.21.0-bugfix }

- The pulp signing task that produces atomic type signature no longer signs cosign signatures,
  attestations and sboms (images that end with .sig, .att, or .sbom), and ignores them instead.
  [#1347](https://github.com/pulp/pulp_container/issues/1347)
- Fixed a bug that caused intermittent failures during the pull-through caching when using non-local
  filesystem storage.
  [#1493](https://github.com/pulp/pulp_container/issues/1493)
- Made the pull-through caching machinery resilient to connection errors.
  [#1499](https://github.com/pulp/pulp_container/issues/1499)
- Pulp Container specific settings are now properly validated during the deployment checks of a Pulp
  instance.
  [#1550](https://github.com/pulp/pulp_container/issues/1550)
- Tasks created after uploading manifests will now remain available for further inspection and will not be deleted.
  [#1602](https://github.com/pulp/pulp_container/issues/1602)
- Disallowed anonymous users to pull images from private pull-through distributions.
  [#1623](https://github.com/pulp/pulp_container/issues/1623)
- Permitted users with the `pull_new_containerdistribution` permission to pull new data via
  pull-through distributions.
  [#1624](https://github.com/pulp/pulp_container/issues/1624)
- Modified the `_catalog` endpoint to allow non-authed users to see all repos in catalog
  (private and public) when token-auth is disabled.
  [#1651](https://github.com/pulp/pulp_container/issues/1651)
- Disallowed anonymous users to pull new content via a pull-through caching distribution. Content that
  is already cached/downloaded can be still pulled.
  [#1657](https://github.com/pulp/pulp_container/issues/1657)

#### Misc {: #2.21.0-misc }

- [#1607](https://github.com/pulp/pulp_container/issues/1607), [#1681](https://github.com/pulp/pulp_container/issues/1681)

---

## 2.20.0 (2024-05-06) {: #2.20.0 }

### Features

-   Updated the Manifest model to no longer rely on artifacts, storing all manifest data internally
    within the database. This change dissociates the manifest from external files on the storage
    backend.
    [#1288](https://github.com/pulp/pulp_container/issues/1288)

### Bugfixes

-   Resolved circular import errors raised when using pulp-container as a library.
    [#1561](https://github.com/pulp/pulp_container/issues/1561)
-   Fixed hande-image-data command to skip content that has labels/annotations already populated.
    [#1573](https://github.com/pulp/pulp_container/issues/1573)
-   Fixed handle-image-data command to update all entries in one run.
    [#1575](https://github.com/pulp/pulp_container/issues/1575)
-   Fixed a bug that disallowed users from leveraging the remote authentication.
    [#1577](https://github.com/pulp/pulp_container/issues/1577)
-   Fixed a bug that caused the registry to not accept requests from anonymous users when token
    authentication was disabled.
    [#1605](https://github.com/pulp/pulp_container/issues/1605)

### Deprecations and Removals

-   Removed the deprecated ADDITIONAL_OCI_ARTIFACT_TYPES setting.
    [#1537](https://github.com/pulp/pulp_container/issues/1537)

### Misc

-   

---

## 2.19.3 (2024-04-23) {: #2.19.3 }

### Bugfixes

-   Fixed hande-image-data command to skip content that has labels/annotations already populated.
    [#1573](https://github.com/pulp/pulp_container/issues/1573)
-   Fixed handle-image-data command to update all entries in one run.
    [#1575](https://github.com/pulp/pulp_container/issues/1575)
-   Fixed a bug that disallowed users from leveraging the remote authentication.
    [#1577](https://github.com/pulp/pulp_container/issues/1577)

---

## 2.19.2 (2024-03-20) {: #2.19.2 }

No significant changes.

---

## 2.19.1 (2024-03-20) {: #2.19.1 }

### Bugfixes

-   Resolved circular import errors raised when using pulp-container as a library.
    [#1561](https://github.com/pulp/pulp_container/issues/1561)

---

## 2.19.0 (2024-03-15) {: #2.19.0 }

### Features

-   Incorporated a notion of container images' characteristics. Users can now filter manifests by their
    nature using the `is_flatpak` or `is_bootable` field on the corresponding Manifest endpoint.
    In addition to that, manifest's annotations and configuration labels were exposed on the same
    endpoint too.
    [#1437](https://github.com/pulp/pulp_container/issues/1437)
-   Updated the OCI manifest schema validation to comply with the changes from the OCI Image Manifest
    Specification.
    [#1494](https://github.com/pulp/pulp_container/issues/1494)

### Bugfixes

-   Fixed sync failure due to ignored certs during registry signature extentions API check.
    [#1552](https://github.com/pulp/pulp_container/issues/1552)

### Improved Documentation

-   Migrated the whole documentation to staging. The documentation should be now consumed from the
    unified docs site.
    [#1517](https://github.com/pulp/pulp_container/issues/1517)

### Deprecations and Removals

-   Removed the optional "kid" parameter stored inside the signatures' payload generated during
    docker manifest v2 schema 1 conversion. This change also removes the `ecdsa` dependency,
    which is vulnerable to Minevra timing attacks.
    [#1485](https://github.com/pulp/pulp_container/issues/1485)
-   Removed the manifest schema conversion machinery. If the manifest is stored locally in the newer
    format and old clients request v2 schema1 manifest they will receive 404. v2 schema1 manifest is
    still going to be mirrored from remote source during sync if available and passed to the old clients
    on the request.
    [#1509](https://github.com/pulp/pulp_container/issues/1509)
-   Deprecated `ADDITIONAL_OCI_ARTIFACT_TYPES` setting in favour of the relaxed validation.
    [#1494](https://github.com/pulp/pulp_container/issues/1494)

---

## 2.18.1 (2024-03-15) {: #2.18.1 }

### Bugfixes

-   Fixed sync failure due to ignored certs during registry signature extentions API check.
    [#1552](https://github.com/pulp/pulp_container/issues/1552)

---

## 2.18.0 (2024-02-02) {: #2.18.0 }

### Features

-   Added support for pull-through caching. Users can now configure a dedicated distribution and remote
    linked to an external registry without the need to create and mirror repositories in advance. Pulp
    downloads missing content automatically if requested and acts as a caching proxy.
    [#507](https://github.com/pulp/pulp_container/issues/507)

### Bugfixes

-   Added `application/vnd.docker.distribution.manifest.v1+prettyjws` to the list of accepted
    media types retrieved from a remote registry.
    [#1444](https://github.com/pulp/pulp_container/issues/1444)

### Misc

-   [#489](https://github.com/pulp/pulp_container/issues/489), [#1275](https://github.com/pulp/pulp_container/issues/1275)

---

## 2.17.0 (2023-11-03) {: #2.17.0 }

### Features

-   Started signing manifests asynchronously. This feature improves the performance of signing tasks.
    Additionally, setting `MAX_PARALLEL_SIGNING_TASKS` was introduced to cap the number of threads
    used for parallel signing (defaults to `10`).
    [#1208](https://github.com/pulp/pulp_container/issues/1208)
-   Adjusted default access policies for new labels API.
    [#1384](https://github.com/pulp/pulp_container/issues/1384)
-   Made pulp_container compatible with pulpcore 3.40.
    [#1399](https://github.com/pulp/pulp_container/issues/1399)

### Bugfixes

-   Fixed re-sync failures after reclaiming disk space.
    [#1400](https://github.com/pulp/pulp_container/issues/1400)

---

## 2.16.9 (2024-07-09) {: #2.16.9 }


#### Bugfixes {: #2.16.9-bugfix }

- Fixed the long accept header limit exceed during sync.
  [#1696](https://github.com/pulp/pulp_container/issues/1696)

---

## 2.16.8 (2024-06-27) {: #2.16.8 }


#### Bugfixes {: #2.16.8-bugfix }

- Fixed a bug that disallowed users from leveraging the remote authentication.
  [#1577](https://github.com/pulp/pulp_container/issues/1577)
- Fixed a bug that caused the registry to not accept requests from anonymous users when token
  authentication was disabled.
  [#1605](https://github.com/pulp/pulp_container/issues/1605)

---

## 2.16.7 (2024-06-21) {: #2.16.7 }


No significant changes.

---

## 2.16.6 (2024-03-15) {: #2.16.6 }

### Bugfixes

-   Fixed sync failure due to ignored certs during registry signature extentions API check.
    [#1552](https://github.com/pulp/pulp_container/issues/1552)

---

## 2.16.5 (2024-02-14) {: #2.16.5 }

### Deprecations and Removals

-   Removed the optional "kid" parameter stored inside the signatures' payload generated during
    docker manifest v2 schema 1 conversion. This change also removes the `ecdsa` dependency,
    which is vulnerable to Minevra timing attacks.
    [#1485](https://github.com/pulp/pulp_container/issues/1485)

---

## 2.16.4 (2024-01-24) {: #2.16.4 }

### Bugfixes

-   Fixed re-sync failures after reclaiming disk space.
    [#1400](https://github.com/pulp/pulp_container/issues/1400)

---

## 2.16.3 (2023-12-15) {: #2.16.3 }

### Bugfixes

-   Added `application/vnd.docker.distribution.manifest.v1+prettyjws` to the list of accepted
    media types retrieved from a remote registry.
    [#1444](https://github.com/pulp/pulp_container/issues/1444)

---

## 2.16.2 (2023-09-09) {: #2.16.2 }

No significant changes.

---

## 2.16.1 (2023-09-09) {: #2.16.1 }

No significant changes.

---

## 2.16.0 (2023-08-02) {: #2.16.0 }

### Features

-   Added OCI artifact support for Helm charts.
    [#464](https://github.com/pulp/pulp_container/issues/464)
-   Added support to serve cosign signatures, SBOMs, and attestations.
    [#1165](https://github.com/pulp/pulp_container/issues/1165)
-   Added support to mirror cosign signatures, SBOMs and attestations.
    [#1166](https://github.com/pulp/pulp_container/issues/1166)
-   Added suport to push cosign signatures, attestations or SBOMs to Pulp Registry.
    [#1167](https://github.com/pulp/pulp_container/issues/1167)
-   Added support for monolithic upload.
    [#1219](https://github.com/pulp/pulp_container/issues/1219)
-   Enabled Pulp registry to support by default some well-known OCI types.
    [#1232](https://github.com/pulp/pulp_container/issues/1232)
-   Added `ADDITIONAL_OCI_ARTIFACT_TYPES` setting to make the list of supported OCI artifact types
    configurable.
    [#1233](https://github.com/pulp/pulp_container/issues/1233)
-   Added support for Flatpak index endpoints.
    [#1315](https://github.com/pulp/pulp_container/issues/1315)

### Bugfixes

-   Taught the Container Registry to accept docker schema2 sub-manifest types in OCI index.
    [#1231](https://github.com/pulp/pulp_container/issues/1231)
-   Fixed a security issue that allowed users without sufficient permissions to mount blobs.
    [#1286](https://github.com/pulp/pulp_container/issues/1286)
-   Ensured downloader during the repair task contains accept headers for the
    manifests to download.
    [#1303](https://github.com/pulp/pulp_container/issues/1303)
-   Disabled TLS validation, if opted out in a remote, when syncing signatures.
    [#1305](https://github.com/pulp/pulp_container/issues/1305)
-   Fixed pulp-to-pulp failing sync with `406 Not Acceptable`.
    [#1329](https://github.com/pulp/pulp_container/issues/1329)

### Improved Documentation

-   Took the import/export feature out of tech preview.
    [#1236](https://github.com/pulp/pulp_container/issues/1236)

---

## 2.15.6 (2024-03-15) {: #2.15.6 }

### Bugfixes

-   Fixed sync failure due to ignored certs during registry signature extentions API check.
    [#1552](https://github.com/pulp/pulp_container/issues/1552)

---

## 2.15.5 (2024-02-15) {: #2.15.5 }

### Deprecations and Removals

-   Removed the optional "kid" parameter stored inside the signatures' payload generated during
    docker manifest v2 schema 1 conversion. This change also removes the `ecdsa` dependency,
    which is vulnerable to Minevra timing attacks.
    [#1485](https://github.com/pulp/pulp_container/issues/1485)

---

## 2.15.4 (2024-01-15) {: #2.15.4 }

### Bugfixes

-   Taught the Container Registry to accept docker schema2 sub-manifest types in OCI index.
    [#1231](https://github.com/pulp/pulp_container/issues/1231)

---

## 2.15.3 (2023-12-15) {: #2.15.3 }

### Bugfixes

-   Fixed re-sync failures after reclaiming disk space.
    [#1400](https://github.com/pulp/pulp_container/issues/1400)
-   Added `application/vnd.docker.distribution.manifest.v1+prettyjws` to the list of accepted
    media types retrieved from a remote registry.
    [#1444](https://github.com/pulp/pulp_container/issues/1444)

---

## 2.15.2 (2023-07-24) {: #2.15.2 }

### Bugfixes

-   Fixed a security issue that allowed users without sufficient permissions to mount blobs.
    [#1286](https://github.com/pulp/pulp_container/issues/1286)
-   Fixed pulp-to-pulp failing sync with `406 Not Acceptable`.
    [#1329](https://github.com/pulp/pulp_container/issues/1329)

---

## 2.15.1 (2023-06-15) {: #2.15.1 }

### Bugfixes

-   Relaxed oci manifest json validation to allow other layer mediaTypes than oci layer type.
    [#1227](https://github.com/pulp/pulp_container/issues/1227)
-   Ensured downloader during the repair task contains accept headers for the
    manifests to download.
    [#1303](https://github.com/pulp/pulp_container/issues/1303)

---

## 2.15.0 (2023-05-26) {: #2.15.0 }

### Features

-   Added support for automatically creating missing repositories during the import procedure. The
    creation is disabled by default. Use `create_repositories=True` to tell Pulp to create missing
    repositories when executing the import procedure.
    [#825](https://github.com/pulp/pulp_container/issues/825)
-   Added a check if a manifest already exists locally to decrease the number of downloads from a remote registry when syncing content.
    [#1047](https://github.com/pulp/pulp_container/issues/1047)
-   Enhanced push operation efficiency by implementing the utilization of ephemeral blobs and
    manifests, eliminating the need for generating unnecessary repository versions.
    [#1212](https://github.com/pulp/pulp_container/issues/1212)
-   Updated compatibility for pulpcore 3.25 and Django 4.2.
    [#1277](https://github.com/pulp/pulp_container/issues/1277)

### Bugfixes

-   Ensured an HTTP 401 response in case a user provides invalid credentials during the login
    (e.g., via `podman login`).
    [#918](https://github.com/pulp/pulp_container/issues/918)
-   Translated v1 signed schema media_type into v1 schema instead.
    [#1045](https://github.com/pulp/pulp_container/issues/1045)
-   Fixed content-disposition header which is used in the object storage backends.
    [#1096](https://github.com/pulp/pulp_container/issues/1096)
-   Fixed an issue that caused all staff users to have superuser permissions when accessing the
    registry without token authentication enabled.
    [#1109](https://github.com/pulp/pulp_container/issues/1109)
-   Fixed a bug where the Podman client could not verify manifest indices signed with a Pulp signing service.
    [#1135](https://github.com/pulp/pulp_container/issues/1135)
-   Fixed a method for determining the media type of manifests when syncing content.
    [#1147](https://github.com/pulp/pulp_container/issues/1147)
-   Added application/octet-stream as an accepted media_type for docker config objects.
    [#1156](https://github.com/pulp/pulp_container/issues/1156)
-   Fixed signing task that could skip some image signing.
    [#1209](https://github.com/pulp/pulp_container/issues/1209)
-   Started triggering only one mount-blob task per upload after back-off.
    [#1211](https://github.com/pulp/pulp_container/issues/1211)
-   Started sanitizing input data when creating namespaces or distributions.
    [#1229](https://github.com/pulp/pulp_container/issues/1229)
-   Fixed a bug that disallowed users to build images that have artifacts within the same directory.
    [#1234](https://github.com/pulp/pulp_container/issues/1234)
-   Fixed a bug that disallowed users to configure custom authentication classes for the token server.
    [#1254](https://github.com/pulp/pulp_container/issues/1254)

### Misc

-   [#1093](https://github.com/pulp/pulp_container/issues/1093), [#1154](https://github.com/pulp/pulp_container/issues/1154)

---

## 2.14.15 (2024-07-09) {: #2.14.15 }


#### Bugfixes {: #2.14.15-bugfix }

- Fixed the long accept header limit exceed during sync.
  [#1696](https://github.com/pulp/pulp_container/issues/1696)

---

## 2.14.14 (2024-06-20) {: #2.14.14 }


No significant changes.

---

## 2.14.13 (2024-03-15) {: #2.14.13 }

### Bugfixes

-   Fixed sync failure due to ignored certs during registry signature extentions API check.
    [#1552](https://github.com/pulp/pulp_container/issues/1552)

---

## 2.14.12 (2024-02-15) {: #2.14.12 }

### Deprecations and Removals

-   Removed the optional "kid" parameter stored inside the signatures' payload generated during
    docker manifest v2 schema 1 conversion. This change also removes the `ecdsa` dependency,
    which is vulnerable to Minevra timing attacks.
    [#1485](https://github.com/pulp/pulp_container/issues/1485)

---

## 2.14.11 (2024-01-30) {: #2.14.11 }

### Bugfixes

-   Disabled TLS validation, if opted out in a remote, when syncing signatures.
    [#1305](https://github.com/pulp/pulp_container/issues/1305)

---

## 2.14.10 (2024-01-15) {: #2.14.10 }

### Bugfixes

-   Taught the Container Registry to accept docker schema2 sub-manifest types in OCI index.
    [#1231](https://github.com/pulp/pulp_container/issues/1231)

---

## 2.14.9 (2023-12-15) {: #2.14.9 }

### Bugfixes

-   Added `application/vnd.docker.distribution.manifest.v1+prettyjws` to the list of accepted
    media types retrieved from a remote registry.
    [#1444](https://github.com/pulp/pulp_container/issues/1444)

---

## 2.14.8 (2023-10-31) {: #2.14.8 }

### Bugfixes

-   Fixed re-sync failures after reclaiming disk space.
    [#1400](https://github.com/pulp/pulp_container/issues/1400)

---

## 2.14.7 (2023-07-24) {: #2.14.7 }

### Bugfixes

-   Fixed a security issue that allowed users without sufficient permissions to mount blobs.
    [#1286](https://github.com/pulp/pulp_container/issues/1286)
-   Fixed pulp-to-pulp failing sync with `406 Not Acceptable`.
    [#1329](https://github.com/pulp/pulp_container/issues/1329)

---

## 2.14.6 (2023-06-15) {: #2.14.6 }

### Bugfixes

-   Ensured an HTTP 401 response in case a user provides invalid credentials during the login
    (e.g., via `podman login`).
    [#918](https://github.com/pulp/pulp_container/issues/918)
-   Started triggering only one mount-blob task per upload after back-off.
    [#1211](https://github.com/pulp/pulp_container/issues/1211)
-   Ensured downloader during the repair task contains accept headers for the
    manifests to download.
    [#1303](https://github.com/pulp/pulp_container/issues/1303)

---

## 2.14.5 (2023-04-11) {: #2.14.5 }

### Bugfixes

-   Fixed a bug that disallowed users to configure custom authentication classes for the token server.
    [#1254](https://github.com/pulp/pulp_container/issues/1254)

---

## 2.14.4 (2023-03-30) {: #2.14.4 }

### Bugfixes

-   Fixed signing task that could skip some image signing.
    [#1209](https://github.com/pulp/pulp_container/issues/1209)
-   Relaxed oci manifest json validation to allow other layer mediaTypes than oci layer type.
    [#1227](https://github.com/pulp/pulp_container/issues/1227)

---

## 2.14.3 (2022-12-02) {: #2.14.3 }

### Bugfixes

-   Fixed a bug where the Podman client could not verify manifest indices signed with a Pulp signing service.
    [#1135](https://github.com/pulp/pulp_container/issues/1135)
-   Fixed a method for determining the media type of manifests when syncing content.
    [#1147](https://github.com/pulp/pulp_container/issues/1147)
-   Added application/octet-stream as an accepted media_type for docker config objects.
    [#1156](https://github.com/pulp/pulp_container/issues/1156)

---

## 2.14.2 (2022-10-22) {: #2.14.2 }

No significant changes.

---

## 2.14.1 (2022-10-07) {: #2.14.1 }

### Bugfixes

-   Translated v1 signed schema media_type into v1 schema instead.
    [#1045](https://github.com/pulp/pulp_container/issues/1045)

---

## 2.14.0 (2022-08-25) {: #2.14.0 }

### Features

-   Added validation for uploaded and synced manifest JSON content.
    [#672](https://github.com/pulp/pulp_container/issues/672)

### Bugfixes

-   Silenced redundant logs when downloading signatures.
    [#518](https://github.com/pulp/pulp_container/issues/518)
-   Silenced redundant GnuPG errors logged while decrypting manifest signatures.
    [#519](https://github.com/pulp/pulp_container/issues/519)
-   Fixed a bug that caused untagged manifests to be tagged by their digest during the push operation.
    [#852](https://github.com/pulp/pulp_container/issues/852)
-   Fixed internal server errors raised when a podman client (<4.0) used invalid content types for
    manifest lists.
    [#853](https://github.com/pulp/pulp_container/issues/853)
-   Fixed a misleading error message raised when a user provided an invalid manifest list.
    [#854](https://github.com/pulp/pulp_container/issues/854)
-   Fixed an error that was raised when an OCI manifest did not contain `mediaType`.
    [#883](https://github.com/pulp/pulp_container/issues/883)
-   Started returning an HTTP 401 response in case of invalid credentials provided by a container
    client (e.g., `podman`).
    [#918](https://github.com/pulp/pulp_container/issues/918)
-   Configured aiohttp to avoid rewriting redirect URLs, as some web servers
    (e.g. Amazon CloudFront) can be tempermental about the encoding of the URL.
    [#919](https://github.com/pulp/pulp_container/issues/919)
-   Fixed the Content-Length key error raised when uploading images.
    [#921](https://github.com/pulp/pulp_container/issues/921)
-   Fixed an HTTP 404 response during sync from registry.redhat.io.
    [#974](https://github.com/pulp/pulp_container/issues/974)
-   Introduced the `pulpcore-manager container-repair-media-type` command to fix incorrect media
    types of manifests that could have been stored in the database as a result of a sync task.
    [#977](https://github.com/pulp/pulp_container/issues/977)

### Misc

-   [#687](https://github.com/pulp/pulp_container/issues/687)

---

## 2.13.3 (2022-09-14) {: #2.13.3 }

### Bugfixes

-   Translated v1 signed schema media_type into v1 schema instead.
    [#1045](https://github.com/pulp/pulp_container/issues/1045)

---

## 2.13.2 (2022-08-24) {: #2.13.2 }

### Bugfixes

-   Fixed an HTTP 404 response during sync from registry.redhat.io.
    [#974](https://github.com/pulp/pulp_container/issues/974)
-   Introduced the `pulpcore-manager container-repair-media-type` command to fix incorrect media
    types of manifests that could have been stored in the database as a result of a sync task.
    [#977](https://github.com/pulp/pulp_container/issues/977)

---

## 2.13.1 (2022-08-02) {: #2.13.1 }

### Bugfixes

-   Fixed an error that was raised when an OCI manifest did not contain `mediaType`.
    [#883](https://github.com/pulp/pulp_container/issues/883)
-   Fixed the Content-Length key error raised when uploading images.
    [#921](https://github.com/pulp/pulp_container/issues/921)

---

## 2.13.0 (2022-06-24) {: #2.13.0 }

### Features

-   Added support for streaming artifacts from object storage.
    [#731](https://github.com/pulp/pulp_container/issues/731)

### Bugfixes

-   Fixed the machinery for building OCI images.
    [#461](https://github.com/pulp/pulp_container/issues/461)
-   Fixed the regular expression for matching base paths in distributions.
    [#756](https://github.com/pulp/pulp_container/issues/756)
-   Fixed generation of the redirect url to the object storage
    [#767](https://github.com/pulp/pulp_container/issues/767)
-   Enforced the reference to manifests from tags. Note that this bugfix introduces a migration that
    removes tags without any reference to the manifests.
    [#789](https://github.com/pulp/pulp_container/issues/789)
-   Improved image upload process from podman/docker clients.
    These clients send data as one big chunk hence we don't need to save it
    as chunk but as an artifact directly.
    [#797](https://github.com/pulp/pulp_container/issues/797)
-   Fixed upload does not exist error during image push operation.
    [#861](https://github.com/pulp/pulp_container/issues/861)

### Improved Documentation

-   Improved the documentation for RBAC by adding a new section for roles and a new section for
    migrating from permissions to roles.
    [#641](https://github.com/pulp/pulp_container/issues/641)

### Misc

-   [#678](https://github.com/pulp/pulp_container/issues/678), [#772](https://github.com/pulp/pulp_container/issues/772), [#791](https://github.com/pulp/pulp_container/issues/791), [#809](https://github.com/pulp/pulp_container/issues/809)

---

## 2.12.3 (2022-08-24) {: #2.12.3 }

### Bugfixes

-   Fixed an error that was raised when an OCI manifest did not contain `mediaType`.
    [#883](https://github.com/pulp/pulp_container/issues/883)
-   Fixed an HTTP 404 response during sync from registry.redhat.io.
    [#974](https://github.com/pulp/pulp_container/issues/974)
-   Introduced the `pulpcore-manager container-repair-media-type` command to fix incorrect media
    types of manifests that could have been stored in the database as a result of a sync task.
    [#977](https://github.com/pulp/pulp_container/issues/977)

---

## 2.12.2 (2022-07-11) {: #2.12.2 }

### Bugfixes

-   Fixed upload does not exist error during image push operation.
    [#861](https://github.com/pulp/pulp_container/issues/861)

---

## 2.12.1 (2022-05-12) {: #2.12.1 }

### Misc

-   [#772](https://github.com/pulp/pulp_container/issues/772)

---

## 2.12.0 (2022-05-05) {: #2.12.0 }

### Features

-   Added more robust validation for unknown fields passed via REST API requests.
    [#475](https://github.com/pulp/pulp_container/issues/475)
-   Added validation for signatures' payloads.
    [#512](https://github.com/pulp/pulp_container/issues/512)
-   Log messages are now not being translated.
    [#690](https://github.com/pulp/pulp_container/issues/690)

### Bugfixes

-   Fixed url of the registry root endpoint during signature source check.
    [#646](https://github.com/pulp/pulp_container/issues/646)
-   Fixed sync of signed content failing with the error [DeclarativeContent' object has no attribute 'd_content']{.title-ref}.
    [#654](https://github.com/pulp/pulp_container/issues/654)
-   Fixed group related creation hooks that failed if no current user could be identified.
    [#673](https://github.com/pulp/pulp_container/issues/673)
-   Fixed other instances of fd leak.
    [#679](https://github.com/pulp/pulp_container/issues/679)
-   Removed Namespace validation.
    Namespaces are managed transparently on behalf of the user.
    [#688](https://github.com/pulp/pulp_container/issues/688)
-   Fixed some tasks that were using /tmp/ instead of the worker working directory.
    [#696](https://github.com/pulp/pulp_container/issues/696)
-   Fixed the reference to a serializer for building images.
    [#718](https://github.com/pulp/pulp_container/issues/718)
-   Fixed the regular expression for matching dockerhub URLs.
    [#736](https://github.com/pulp/pulp_container/issues/736)

### Improved Documentation

-   Added docs for client signature verification policy.
    [#530](https://github.com/pulp/pulp_container/issues/530)

### Misc

-   [#486](https://github.com/pulp/pulp_container/issues/486), [#495](https://github.com/pulp/pulp_container/issues/495), [#606](https://github.com/pulp/pulp_container/issues/606), [#640](https://github.com/pulp/pulp_container/issues/640), [#665](https://github.com/pulp/pulp_container/issues/665)

---

## 2.11.2 (2022-08-24) {: #2.11.2 }

### Bugfixes

-   Fixed an error that was raised when an OCI manifest did not contain `mediaType`.
    [#883](https://github.com/pulp/pulp_container/issues/883)
-   Fixed an HTTP 404 response during sync from registry.redhat.io.
    [#974](https://github.com/pulp/pulp_container/issues/974)
-   Introduced the `pulpcore-manager container-repair-media-type` command to fix incorrect media
    types of manifests that could have been stored in the database as a result of a sync task.
    [#977](https://github.com/pulp/pulp_container/issues/977)

---

## 2.11.1 (2022-07-12) {: #2.11.1 }

### Bugfixes

-   Fixed sync of signed content failing with the error [DeclarativeContent' object has no attribute 'd_content']{.title-ref}.
    [#654](https://github.com/pulp/pulp_container/issues/654)
-   Fixed group related creation hooks that failed if no current user could be identified.
    [#673](https://github.com/pulp/pulp_container/issues/673)
-   Fixed some tasks that were using /tmp/ instead of the worker working directory.
    [#696](https://github.com/pulp/pulp_container/issues/696)
-   Fixed upload does not exist error during image push operation.
    [#861](https://github.com/pulp/pulp_container/issues/861)

---

## 2.11.0 (2022-03-16) {: #2.11.0 }

### Features

-   Allow upload of non-distributable layers.
    [#462](https://github.com/pulp/pulp_container/issues/462)
-   Added support for pushing manifest lists via the Registry API.
    [#469](https://github.com/pulp/pulp_container/issues/469)
-   Added support for cross repository blob mount.
    [#494](https://github.com/pulp/pulp_container/issues/494)
-   Added support for caching responses from the registry. The caching is not enabled by default.
    Enable it by configuring the Redis connection and defining `CACHE_ENABLED = True` in the
    settings file.
    [#496](https://github.com/pulp/pulp_container/issues/496)
-   Added model, serializer, filter and viewset for image manifest signature.
    Added ability to sync manifest signatures from a sigstore.
    [#498](https://github.com/pulp/pulp_container/issues/498)
-   Added ability to sign container images from within The Pulp Registry.
    manifest_signing_service is used to produce signed container content.
    [#500](https://github.com/pulp/pulp_container/issues/500)
-   Added support for pushing image signatures to the Pulp Registry. The signatures can be pushed by
    utilizing the extensions API.
    [#502](https://github.com/pulp/pulp_container/issues/502)
-   Added an extensions API endpoint for downloading image signatures.
    [#504](https://github.com/pulp/pulp_container/issues/504)
-   Enabled users to import/export image signatures.
    [#506](https://github.com/pulp/pulp_container/issues/506)
-   Ported RBAC implementation to use pulpcore roles.
    [#508](https://github.com/pulp/pulp_container/issues/508)
-   Added recursive removal of manifest signatures when a manifest is removed from a repository.
    [#511](https://github.com/pulp/pulp_container/issues/511)
-   Added support for syncing signatures using docker API extension.
    [#528](https://github.com/pulp/pulp_container/issues/528)
-   Added ability to remove signatures from a container(push) repo.
    [#548](https://github.com/pulp/pulp_container/issues/548)
-   Don't reject manifest that has non-distributable layers during upload.
    [#598](https://github.com/pulp/pulp_container/issues/598)

### Bugfixes

-   Don't store blob's media_type on the model.
    There is no way to say what mimetype it has when it comes into the registry.
    [#493](https://github.com/pulp/pulp_container/issues/493)
-   Account for case when token's scope does not contain type/resource/action.
    [#509](https://github.com/pulp/pulp_container/issues/509)
-   Fixed content retrieval from distribution when repo is removed.
    [#513](https://github.com/pulp/pulp_container/issues/513)
-   Fixed file descriptor leak during image push.
    [#523](https://github.com/pulp/pulp_container/issues/523)
-   Fixed "manifest_id" violates not-null constraint error during sync.
    [#537](https://github.com/pulp/pulp_container/issues/537)
-   Fixed error during container image push.
    [#542](https://github.com/pulp/pulp_container/issues/542)
-   Return a more concise message exception on 500 during image pull when content is missing on the FS.
    [#555](https://github.com/pulp/pulp_container/issues/555)
-   Fixed a bug that disallowed users who were authenticated by a remote webserver to access the
    Registry API endpoints when token authentication was disabled.
    [#558](https://github.com/pulp/pulp_container/issues/558)
-   Successfully re-upload artifact in case it was previously removed.
    [#595](https://github.com/pulp/pulp_container/issues/595)
-   Fixed check for the signature source location.
    [#617](https://github.com/pulp/pulp_container/issues/617)
-   Accept token under access_token for compat reasons.
    [#619](https://github.com/pulp/pulp_container/issues/619)

### Misc

-   [#561](https://github.com/pulp/pulp_container/issues/561)

---

## 2.10.13 (2024-02-15) {: #2.10.13 }

### Deprecations and Removals

-   Removed the optional "kid" parameter stored inside the signatures' payload generated during
    docker manifest v2 schema 1 conversion. This change also removes the `ecdsa` dependency,
    which is vulnerable to Minevra timing attacks.
    [#1485](https://github.com/pulp/pulp_container/issues/1485)

---

## 2.10.12 (2023-02-28) {: #2.10.12 }

### Bugfixes

-   Fixed a method for determining the media type of manifests when syncing content.
    [#1147](https://github.com/pulp/pulp_container/issues/1147)

---

## 2.10.11 (2023-01-11) {: #2.10.11 }

### Bugfixes

-   Fixed container repo sync failure 'null value in column "image_manifest_id" violates not-null constraint'.
    [#1190](https://github.com/pulp/pulp_container/issues/1190)

---

## 2.10.10 (2022-10-20) {: #2.10.10 }

### Bugfixes

-   Fixed a database error raised when creating a distribution with a long base_path.
    [#1103](https://github.com/pulp/pulp_container/issues/1103)

---

## 2.10.9 (2022-09-14) {: #2.10.9 }

### Bugfixes

-   Translated v1 signed schema media_type into v1 schema instead.
    [#1045](https://github.com/pulp/pulp_container/issues/1045)

---

## 2.10.8 (2022-08-24) {: #2.10.8 }

### Bugfixes

-   Fixed an HTTP 404 response during sync from registry.redhat.io.
    [#974](https://github.com/pulp/pulp_container/issues/974)
-   Introduced the `pulpcore-manager container-repair-media-type` command to fix incorrect media
    types of manifests that could have been stored in the database as a result of a sync task.
    [#977](https://github.com/pulp/pulp_container/issues/977)

---

## 2.10.7 (2022-08-16) {: #2.10.7 }

No significant changes.

---

## 2.10.6 (2022-08-15) {: #2.10.6 }

No significant changes.

---

## 2.10.5 (2022-08-02) {: #2.10.5 }

### Bugfixes

-   Fixed an error that was raised when an OCI manifest did not contain `mediaType`.
    [#883](https://github.com/pulp/pulp_container/issues/883)

---

## 2.10.4 (2022-07-11) {: #2.10.4 }

### Bugfixes

-   Fixed upload does not exist error during image push operation.
    [#861](https://github.com/pulp/pulp_container/issues/861)

---

## 2.10.3 (2022-04-05) {: #2.10.3 }

### Bugfixes

-   Accept token under access_token for compat reasons.
    [#619](https://github.com/pulp/pulp_container/issues/619)
-   Fixed group related creation hooks that failed if no current user could be identified.
    [#673](https://github.com/pulp/pulp_container/issues/673)

---

## 2.10.2 (2022-03-04) {: #2.10.2 }

### Bugfixes

-   Return a more concise message exception on 500 during image pull when content is missing on the FS.
    [#555](https://github.com/pulp/pulp_container/issues/555)
-   Successfully re-upload artifact in case it was previously removed.
    [#595](https://github.com/pulp/pulp_container/issues/595)

---

## 2.10.1 (2022-02-15) {: #2.10.1 }

### Bugfixes

-   Fixed file descriptor leak during image push.
    [#523](https://github.com/pulp/pulp_container/issues/523)
-   Fixed "manifest_id" violates not-null constraint error during sync.
    [#537](https://github.com/pulp/pulp_container/issues/537)
-   Fixed error during container image push.
    [#542](https://github.com/pulp/pulp_container/issues/542)

---

## 2.10.0 (2021-12-14) {: #2.10.0 }

### Features

-   Enabled Azure storage backend support.
    [#9488](https://pulp.plan.io/issues/9488)
-   Enabled rate_limit option on the remote. Rate limit defines N req/sec per connection.
    [#9607](https://pulp.plan.io/issues/9607)

---

## 2.9.10 (2023-02-28) {: #2.9.10 }

### Bugfixes

-   Fixed a method for determining the media type of manifests when syncing content.
    [#1147](https://github.com/pulp/pulp_container/issues/1147)
-   Fixed container repo sync failure 'null value in column "image_manifest_id" violates not-null constraint'.
    [#1190](https://github.com/pulp/pulp_container/issues/1190)

---

## 2.9.9 (2022-10-20) {: #2.9.9 }

### Bugfixes

-   Fixed a database error raised when creating a distribution with a long base_path.
    [#1103](https://github.com/pulp/pulp_container/issues/1103)

---

## 2.9.8 (2022-09-14) {: #2.9.8 }

### Bugfixes

-   Translated v1 signed schema media_type into v1 schema instead.
    [#1045](https://github.com/pulp/pulp_container/issues/1045)

---

## 2.9.7 (2022-08-24) {: #2.9.7 }

### Bugfixes

-   Fixed an HTTP 404 response during sync from registry.redhat.io.
    [#974](https://github.com/pulp/pulp_container/issues/974)
-   Introduced the `pulpcore-manager container-repair-media-type` command to fix incorrect media
    types of manifests that could have been stored in the database as a result of a sync task.
    [#977](https://github.com/pulp/pulp_container/issues/977)

---

## 2.9.6 (2022-08-02) {: #2.9.6 }

### Bugfixes

-   Fixed an error that was raised when an OCI manifest did not contain `mediaType`.
    [#883](https://github.com/pulp/pulp_container/issues/883)

---

## 2.9.5 (2022-07-11) {: #2.9.5 }

### Bugfixes

-   Accept token under access_token for compat reasons.
    [#619](https://github.com/pulp/pulp_container/issues/619)
-   Fixed upload does not exist error during image push operation.
    [#861](https://github.com/pulp/pulp_container/issues/861)

---

## 2.9.4 (2022-03-04) {: #2.9.4 }

### Bugfixes

-   Return a more concise message exception on 500 during image pull when content is missing on the FS.
    [#555](https://github.com/pulp/pulp_container/issues/555)
-   Successfully re-upload artifact in case it was previously removed.
    [#595](https://github.com/pulp/pulp_container/issues/595)

---

## 2.9.3 (2022-02-15) {: #2.9.3 }

### Bugfixes

-   Fixed file descriptor leak during image push.
    [#523](https://github.com/pulp/pulp_container/issues/523)
-   Fixed error during container image push.
    [#542](https://github.com/pulp/pulp_container/issues/542)
-   Fixed rate_limit option on the remote. Rate limit defines N req/sec per connection.
    [#578](https://github.com/pulp/pulp_container/issues/578)
-   Fixed a bug that caused container clients to be unable to interact with content stored on S3.
    [#579](https://github.com/pulp/pulp_container/issues/579)

---

## 2.9.2 (2022-02-08) {: #2.9.2 }

### Bugfixes

-   Added validation for the supported manifests and blobs media_types in the push operation.
    [#8303](https://pulp.plan.io/issues/8303)
-   Fixed ORM calls in the content app that were made in async context to use sync_to_async.
    [#9454](https://pulp.plan.io/issues/9454)
-   Fixed a failure during distribution update that occured when unsetting repository_version.
    [#9497](https://pulp.plan.io/issues/9497)
-   Corrected value of `Content-Length` header for push upload responses.
    This fixes the *upstream prematurely closed connection while reading upstream* error that would
    appear in nginx logs after a push operation.
    [#9516](https://pulp.plan.io/issues/9516)
-   Fixed headers and status codes in the upload/blob responses during image push.
    [#9568](https://pulp.plan.io/issues/9568)
-   Send proper blob content_type header when the blob is served.
    [#9571](https://pulp.plan.io/issues/9571)
-   Fixed a bug that caused container clients to be unable to interact with content stored on S3.
    [#9586](https://pulp.plan.io/issues/9586)
-   Fixed a bug, where permissions were checked against the wrong object type.
    [#9589](https://pulp.plan.io/issues/9589)

### Misc

-   [#9562](https://pulp.plan.io/issues/9562), [#9618](https://pulp.plan.io/issues/9618)

---

## 2.9.1 (2021-11-23) {: #2.9.1 }

### Bugfixes

-   Fixed ORM calls in the content app that were made in async context to use sync_to_async.
    (Backported from <https://pulp.plan.io/issues/9454>).
    [#9538](https://pulp.plan.io/issues/9538)
-   Corrected value of `Content-Length` header for push upload responses.
    This fixes the *upstream prematurely closed connection while reading upstream* error that would
    appear in nginx logs after a push operation (Backported from <https://pulp.plan.io/issues/9516>).
    [#9539](https://pulp.plan.io/issues/9539)
-   Fixed Azure storage backend support (Backported from <https://pulp.plan.io/issues/9488>).
    [#9540](https://pulp.plan.io/issues/9540)

---

## 2.9.0 (2021-10-06) {: #2.9.0 }

### Bugfixes

-   Switched from `condition` element to `condition_expression` for boolean logic evaluation to
    support latest drf-access-policy.
    [#9092](https://pulp.plan.io/issues/9092)
-   Fix OpenAPI schema view
    [#9258](https://pulp.plan.io/issues/9258)
-   Refactor sync pipeline to fix a race condition with multiple synchronous syncs.
    [#9292](https://pulp.plan.io/issues/9292)
-   Added validation for a repository base path.
    [#9403](https://pulp.plan.io/issues/9403)

### Misc

-   [#9187](https://pulp.plan.io/issues/9187), [#9203](https://pulp.plan.io/issues/9203), [#9310](https://pulp.plan.io/issues/9310), [#9385](https://pulp.plan.io/issues/9385), [#9466](https://pulp.plan.io/issues/9466)

---

## 2.8.9 (2022-12-13) {: #2.8.9 }

### Bugfixes

-   Fixed a bug that led Pulp to run out of DB connections during podman pull operations.
    [#1146](https://github.com/pulp/pulp_container/issues/1146)

---

## 2.8.8 (2022-08-24) {: #2.8.8 }

### Bugfixes

-   Fixed an HTTP 404 response during sync from registry.redhat.io.
    [#974](https://github.com/pulp/pulp_container/issues/974)

---

## 2.8.7 (2022-04-05) {: #2.8.7 }

### Bugfixes

-   Accept token under access_token for compat reasons.
    [#619](https://github.com/pulp/pulp_container/issues/619)

---

## 2.8.6 (2022-03-04) {: #2.8.6 }

### Bugfixes

-   Return a more concise message exception on 500 during image pull when content is missing on the FS.
    [#555](https://github.com/pulp/pulp_container/issues/555)
-   Successfully re-upload artifact in case it was previously removed.
    [#595](https://github.com/pulp/pulp_container/issues/595)

---

## 2.8.5 (2022-02-15) {: #2.8.5 }

### Bugfixes

-   Fixed file descriptor leak during image push.
    [#523](https://github.com/pulp/pulp_container/issues/523)
-   Fixed error during container image push.
    [#542](https://github.com/pulp/pulp_container/issues/542)

---

## 2.8.4 (2022-01-27) {: #2.8.4 }

### Bugfixes

-   Fixed "manifest_id" violates not-null constraint error during sync.
    [#537](https://github.com/pulp/pulp_container/issues/537)

---

## 2.8.3 (2021-12-09) {: #2.8.3 }

### Bugfixes

-   Fixed a bug that caused container clients to be unable to interact with content stored on S3.
    (Backported from <https://pulp.plan.io/issues/9586>).
    [#9601](https://pulp.plan.io/issues/9601)
-   Fixed rate_limit option on the remote which was ignored during the downloads. Rate limit defines
    N req/sec per connection ( backported from <https://pulp.plan.io/issues/9610>).
    [#9610](https://pulp.plan.io/issues/9610)

---

## 2.8.2 (2021-11-23) {: #2.8.2 }

### Bugfixes

-   Corrected value of `Content-Length` header for push upload responses.
    This fixes the *upstream prematurely closed connection while reading upstream* error that would
    appear in nginx logs after a push operation (Backported from <https://pulp.plan.io/issues/9516>).
    [#9521](https://pulp.plan.io/issues/9521)
-   Fixed ORM calls in the content app that were made in async context to use loop.run_in_executor().
    [#9522](https://pulp.plan.io/issues/9522)
-   Fixed Azure storage backend support (Backported from <https://pulp.plan.io/issues/9488>).
    [#9523](https://pulp.plan.io/issues/9523)
-   Added validation for a repository base path (Backported from <https://pulp.plan.io/issues/9403>).
    [#9526](https://pulp.plan.io/issues/9526)

---

## 2.8.1 (2021-09-07) {: #2.8.1 }

### Bugfixes

-   Refactor sync pipeline to fix a race condition with multiple synchronous syncs.
    (backported from #9292)
    [#9334](https://pulp.plan.io/issues/9334)

---

## 2.8.0 (2021-08-04) {: #2.8.0 }

### Features

-   Add model resources to allow pulp import export handle pulp_container content units for synced container repositories.
    [#6636](https://pulp.plan.io/issues/6636)
-   Enable reclaim disk space feature for blobs and manifests.This feature is available with pulpcore 3.15+
    [#9169](https://pulp.plan.io/issues/9169)

### Bugfixes

-   Use proxy auth credentials when syncing content from a Remote.
    [#9065](https://pulp.plan.io/issues/9065)

### Deprecations and Removals

-   Dropped support for Python 3.6 and 3.7. pulp_container now supports Python 3.8+.
    [#9035](https://pulp.plan.io/issues/9035)

### Misc

-   [#9134](https://pulp.plan.io/issues/9134)

---

## 2.7.1 (2021-07-21) {: #2.7.1 }

### Bugfixes

-   Use proxy auth credentials when syncing content from a Remote.
    (backported from #9065)
    [#9067](https://pulp.plan.io/issues/9067)

---

## 2.7.0 (2021-07-01) {: #2.7.0 }

### Features

-   As a user I can update container push repositories.
    [#8313](https://pulp.plan.io/issues/8313)

### Bugfixes

-   Updated distribution creation policy.
    [#8244](https://pulp.plan.io/issues/8244)
-   Improved error logging on failed image push.
    [#8879](https://pulp.plan.io/issues/8879)
-   Fixed access policy for the container repository `repair` endpoint.
    [#8884](https://pulp.plan.io/issues/8884)

---

## 2.6.0 (2021-05-20) {: #2.6.0 }

### Features

-   Added ability for users to add a Remote to a Repository that is used by default when syncing.
    [#7795](https://pulp.plan.io/issues/7795)

### Bugfixes

-   Fixed a bug where image push of the same tag with docker client ended up in the different manifest upload.
    Updated Range header in the blob upload response so it is inclusive.
    [#8543](https://pulp.plan.io/issues/8543)
-   Add a fix to prevent server errors on push of new repositories including multiple layers.
    [#8565](https://pulp.plan.io/issues/8565)
-   Fixed apache snippet config and removed scheme
    [#8573](https://pulp.plan.io/issues/8573)
-   Do not suggest a time to wait on 429 responses. This allows clients to decide to play nice and increase backoff times.
    [#8576](https://pulp.plan.io/issues/8576)
-   Fix a bug where users with container.namespace_change_containerdistribution couldn't change distributions.
    [#8618](https://pulp.plan.io/issues/8618)
-   Fixed compution of the digest string during the manifest conversion so it also contains the algorithm.
    [#8629](https://pulp.plan.io/issues/8629)
-   Create and return empty_blob on the fly.
    [#8631](https://pulp.plan.io/issues/8631)
-   Fixed "connection already closed" error in the Registry handler.
    [#8672](https://pulp.plan.io/issues/8672)

### Improved Documentation

-   Fixed broken links to API guide
    [#8125](https://pulp.plan.io/issues/8125)

### Misc

-   [#8581](https://pulp.plan.io/issues/8581)

---

## 2.5.5 (2022-02-15) {: #2.5.5 }

### Bugfixes

-   Fixed file descriptor leak during image push.
    [#523](https://pulp.plan.io/issues/523)
-   Fixed error during container image push.
    [#542](https://pulp.plan.io/issues/542)

---

## 2.5.4 (2021-12-14) {: #2.5.4 }

### Bugfixes

-   Improved error logging on failed image push. (Backported from <https://pulp.plan.io/issues/8879>).
    [#8888](https://pulp.plan.io/issues/8888)
-   Fixed access policy for the container repository `repair` endpoint. (Backported from <https://pulp.plan.io/issues/8884>).
    [#8889](https://pulp.plan.io/issues/8889)
-   Fixed a bug that caused container clients to be unable to interact with content stored on S3.
    (Backported from <https://pulp.plan.io/issues/9586>).
    [#9600](https://pulp.plan.io/issues/9600)

---

## 2.5.3 (2021-05-20) {: #2.5.3 }

### Bugfixes

-   Fixed "connection already closed" error in the Registry handler.
    (backported from #8672)
    [#8697](https://pulp.plan.io/issues/8697)
-   Fixed compution of the digest string during the manifest conversion so it also contains the algorithm.
    (backported from #8629)
    [#8698](https://pulp.plan.io/issues/8698)
-   Create and return empty_blob on the fly.
    (backported from #8631)
    [#8699](https://pulp.plan.io/issues/8699)
-   Do not suggest a time to wait on 429 responses. This allows clients to decide to play nice and increase backoff times (Backported from #8576).
    [#8703](https://pulp.plan.io/issues/8703)

---

## 2.5.2 (2021-04-19) {: #2.5.2 }

### Bugfixes

-   Add a fix to prevent server errors on push of new repositories including multiple layers. (Backported from <https://pulp.plan.io/issues/8565>)
    [#8591](https://pulp.plan.io/issues/8591)

---

## 2.5.1 (2021-04-13) {: #2.5.1 }

### Bugfixes

-   Fixed a bug where image push of the same tag with docker client ended up in the different manifest upload.
    Updated Range header in the blob upload response so it is inclusive. (Backported from <https://pulp.plan.io/issues/8543>)
    [#8545](https://pulp.plan.io/issues/8545)

---

## 2.5.0 (2021-04-08) {: #2.5.0 }

### Features

-   Updated the catalog endpoint to show only repositories that users have permissions to pull from.
    [#8068](https://pulp.plan.io/issues/8068)
-   Config blob is downloaded always, regardless of the remote's settings.
    [#8319](https://pulp.plan.io/issues/8319)

### Bugfixes

-   Wrapped the repository version creation during blob upload commit in a task that will be waited on by issuing 429.
    [#8151](https://pulp.plan.io/issues/8151)

### Improved Documentation

-   Released container RBAC from tech-preview.
    [#8527](https://pulp.plan.io/issues/8527)

---

## 2.4.0 (2021-03-18) {: #2.4.0 }

### Features

-   Added pagination to the _catalog and the tags/list endpoint in the registry API.
    [#7974](https://pulp.plan.io/issues/7974)
-   Added a fall back to use BasicAuth if TOKEN_AUTH_DISABLED is set.
    [#8074](https://pulp.plan.io/issues/8074)
-   Added a new API endpoint that allows users to remove an image by a digest from a push repository.
    [#8105](https://pulp.plan.io/issues/8105)
-   Added a namespace_is_username helper to decide whether the namespace matches the username of the requests user.
    Changed the namespace access_policy to allow users without permissions to create the namespace that matches their username.
    [#8197](https://pulp.plan.io/issues/8197)

### Bugfixes

-   Fixed the `scope` field returned by the registry when a user was accessing the catalong endpoint without a token. In addition to that, the field `access` returned by the token server for the root endpoint was fixed as well.
    [#8045](https://pulp.plan.io/issues/8045)
-   Added missing error code that should be returned in the WWW-Authenticate header.
    [#8046](https://pulp.plan.io/issues/8046)
-   Fixed a bug that caused the registry to fail during the schema conversion when there was not
    provided the field `created_by`.
    [#8299](https://pulp.plan.io/issues/8299)
-   Prevent the registry pagination classes to fail if a negative page size is requested.
    [#8318](https://pulp.plan.io/issues/8318)

---

## 2.3.1 (2021-02-15) {: #2.3.1 }

### Bugfixes

-   Use `get_user_model()` to prevent pulp_container from crashing when running alongside other pulp plugins that override the default user authentication models.
    [#8260](https://pulp.plan.io/issues/8260)

---

## 2.3.0 (2021-02-08) {: #2.3.0 }

### Features

-   Added access policy and permission management to container repositories.
    [#7706](https://pulp.plan.io/issues/7706)
-   Added access policy and permission management to the container remotes.
    [#7707](https://pulp.plan.io/issues/7707)
-   Added access policy for ContainerDistributionViewSet and the Registry API.
    [#7937](https://pulp.plan.io/issues/7937)
-   Added access policy and permission management to the container namespaces.
    [#7967](https://pulp.plan.io/issues/7967)
-   Added RBAC to the push repository endpoint.
    [#7968](https://pulp.plan.io/issues/7968)
-   Add RBAC to the repository version endpoints.
    [#8017](https://pulp.plan.io/issues/8017)
-   Made the push and pull permission granting use the `ContainerDistribution` access policy.
    [#8075](https://pulp.plan.io/issues/8075)
-   Added Owner, Collaborator, and Consumer groups and permissions for Namespaces and Repositories.
    [#8101](https://pulp.plan.io/issues/8101)
-   Added a private flag to mark distributions global read accessability.
    [#8102](https://pulp.plan.io/issues/8102)
-   Added support for tagging and untagging manifests for push repositories.
    [#8104](https://pulp.plan.io/issues/8104)
-   Added RBAC for container content.
    [#8142](https://pulp.plan.io/issues/8142)
-   Made the token expiration time configurable via the setting 'TOKEN_EXPIRATION_TIME'.
    [#8147](https://pulp.plan.io/issues/8147)
-   Decoupled permissions for registry live api and pulp api.
    [#8153](https://pulp.plan.io/issues/8153)
-   Add description field to the ContainerDistribution.
    [#8168](https://pulp.plan.io/issues/8168)

### Bugfixes

-   Fixed a bug that caused the registry to advertise an invalid digest of a converted manifest.
    [#7923](https://pulp.plan.io/issues/7923)
-   Fixed the way how the plugin verifies authenticated users in the token authentication.
    [#8057](https://pulp.plan.io/issues/8057)
-   Adjusted the queryset filtering of `ContainerDistribution` to include `private` and `Namespace` permissions.
    [#8206](https://pulp.plan.io/issues/8206)
-   Fixed bug experienced when pulling using docker 20.10 client.
    [#8208](https://pulp.plan.io/issues/8208)

### Deprecations and Removals

-   POST and DELETE requests are no longer available for /pulp/api/v3/repositories/container/container-push/.
    Push repositories are still automatically created via docker/podman push and deleted through container distributions.
    [#8014](https://pulp.plan.io/issues/8014)

### Misc

-   [#7936](https://pulp.plan.io/issues/7936)

---

## 2.2.2 (2021-05-26) {: #2.2.2 }

### Bugfixes

-   Fixed compution of the digest string during the manifest conversion so it also contains the algorithm. (Backported from <https://pulp.plan.io/issues/8629>).
    [#8818](https://pulp.plan.io/issues/8818)
-   Create and return empty_blob on the fly. (Backported from <https://pulp.plan.io/issues/8654>).
    [#8819](https://pulp.plan.io/issues/8819)
-   Fixed "connection already closed" error in the Registry handler. (Backported from <https://pulp.plan.io/issues/8672>).
    [#8820](https://pulp.plan.io/issues/8820)

---

## 2.2.1 (2021-03-18) {: #2.2.1 }

### Bugfixes

-   Fixed a bug that caused the registry to fail during the schema conversion when there was not
    provided the field `created_by`. (Backported from <https://pulp.plan.io/issues/8299>)
    [#8349](https://pulp.plan.io/issues/8349)
-   Fixed a bug that caused the registry to advertise an invalid digest of a converted manifest. (Backported from <https://pulp.plan.io/issues/7923>)
    [#8350](https://pulp.plan.io/issues/8350)
-   Fixed bug experienced when pulling using docker 20.10 client. (Backported from <https://pulp.plan.io/issues/8208>)
    [#8367](https://pulp.plan.io/issues/8367)

---

## 2.2.0 (2020-12-09) {: #2.2.0 }

### Features

-   Added namespaces to group repositories and distributions.
    [#7089](https://pulp.plan.io/issues/7089)
-   Refactored the registry's push API to not store uploaded chunks in /var/lib/pulp, but rather
    in the shared storage.
    [#7218](https://pulp.plan.io/issues/7218)

### Bugfixes

-   Fixed the value of registry_path in a container distribution.
    [#7385](https://pulp.plan.io/issues/7385)
-   Added validation for tags' names.
    [#7506](https://pulp.plan.io/issues/7506)
-   Fixed Renderer to handle properly Manifest and Blob responses.
    [#7620](https://pulp.plan.io/issues/7620)
-   Updated models fields to not use settings directly.
    [#7728](https://pulp.plan.io/issues/7728)
-   Fixed a bug where Artifacts were missing sha224 checksum after podman push.
    [#7774](https://pulp.plan.io/issues/7774)

### Improved Documentation

-   Updated scripts to correctly show the workflows.
    [#7547](https://pulp.plan.io/issues/7547)

### Misc

-   [#7649](https://pulp.plan.io/issues/7649)

---

## 2.1.3 (2022-05-12) {: #2.1.3 }

### Misc

-   [#744](https://github.com/pulp/pulp_container/issues/744)

---

## 2.1.2 (2021-05-04) {: #2.1.2 }

### Bugfixes

-   Create and return empty_blob on the fly (Backported from <https://pulp.plan.io/issues/8631>)
    [#8654](https://pulp.plan.io/issues/8654)
-   Fixed compution of the digest string during the manifest conversion so it also contains the algorithm (Backported from <https://pulp.plan.io/issues/8629>).
    [#8655](https://pulp.plan.io/issues/8655)
-   Fixed "connection already closed" error in the Registry handler (Backported from <https://pulp.plan.io/issues/8672>).
    [#8685](https://pulp.plan.io/issues/8685)

---

## 2.1.1 (2021-03-08) {: #2.1.1 }

### Bugfixes

-   Fixed Renderer to handle properly Manifest and Blob responses. (Backported from <https://pulp.plan.io/issues/7620>)
    [#8346](https://pulp.plan.io/issues/8346)
-   Fixed a bug that caused the registry to advertise an invalid digest of a converted manifest. (Backported from <https://pulp.plan.io/issues/7923>)
    [#8347](https://pulp.plan.io/issues/8347)
-   Fixed a bug that caused the registry to fail during the schema conversion when there was not
    provided the field `created_by`. (Backported from <https://pulp.plan.io/issues/8299>)
    [#8348](https://pulp.plan.io/issues/8348)
-   Fixed bug experienced when pulling using docker 20.10 client. (Backported from <https://pulp.plan.io/issues/8208>)
    [#8366](https://pulp.plan.io/issues/8366)

---

## 2.1.0 (2020-09-23) {: #2.1.0 }

### Bugfixes

-   Fixed the unnecessary double redirect issued for the S3 storage
    [#6826](https://pulp.plan.io/issues/6826)

### Improved Documentation

-   Documented how include/exclude_tags options work with mirror=True/False.
    [#7380](https://pulp.plan.io/issues/7380)

---

## 2.0.1 (2020-09-08) {: #2.0.1 }

### Bugfixes

-   Fixed bug where users would get 403 response when pulling from the registry running behind an HTTPS
    reverse proxy.
    [#7462](https://pulp.plan.io/issues/7462)

---

## 2.0.0 (2020-08-18) {: #2.0.0 }

### Features

-   Added 'exclude_tags' to support e.g. skipping source containers in sync.
    [#6922](https://pulp.plan.io/issues/6922)
-   Push repositories will be deleted together with their attached distribution.
    [#7172](https://pulp.plan.io/issues/7172)

### Bugfixes

-   Updated the sync machinery to not store an image manifest as a tag's artifact
    [#6816](https://pulp.plan.io/issues/6816)
-   Added a validation, that a push repository cannot be distributed by specifying a version.
    [#7012](https://pulp.plan.io/issues/7012)
-   Forbid the REST API methods PATCH and PUT to prevent changes to repositories created via
    docker/podman push requests
    [#7013](https://pulp.plan.io/issues/7013)
-   Fixed the rendering of errors in the container registry api.
    [#7054](https://pulp.plan.io/issues/7054)
-   Repaired broken registry with TOKEN_AUTH_DISABLED=True
    [#7304](https://pulp.plan.io/issues/7304)

### Improved Documentation

-   Updated docs for 2.0 GA.
    [#7317](https://pulp.plan.io/issues/7317)

### Deprecations and Removals

-   Renamed 'whitelist_tags' to 'include_tags'.
    [#7070](https://pulp.plan.io/issues/7070)

---

## 2.0.0b3 (2020-07-16)

### Features

-   Redirected get on Manifest get to the content app to enable schema conversion.
    Repaired schema conversion to work with django-storage framework.
    [#6824](https://pulp.plan.io/issues/6824)
-   Added ContainerPushRepository type to back writeable container registries.
    [#6825](https://pulp.plan.io/issues/6825)
-   Added ContentRedirectContentGuard to redirect with preauthenticated urls to the content app.
    [#6894](https://pulp.plan.io/issues/6894)
-   Restricted push access to admin user.
    [#6976](https://pulp.plan.io/issues/6976)

### Bugfixes

-   Refactored token_authentication that now happens in pulpcore-api app
    [#6894](https://pulp.plan.io/issues/6894)
-   Fixed a crash when trying to access content with an unparseable token.
    [#7124](https://pulp.plan.io/issues/7124)
-   Fixed a runtime error which was triggered when a registry client sends an accept header with an
    inappropriate media type for a manifest and the conversion failed.
    [#7125](https://pulp.plan.io/issues/7125)

### Misc

-   [#5302](https://pulp.plan.io/issues/5302)

---

## 2.0.0b2 (2020-06-08)

### Bugfixes

-   Fixed the client_max_body_size value in the nginx config.
    [#6916](https://pulp.plan.io/issues/6916)

---

## 2.0.0b1 (2020-06-03)

### Features

-   Added REST APIs for handling docker/podman push.
    [#5027](https://pulp.plan.io/issues/5027)

### Bugfixes

-   Fixed 500 error when pulling by tag.
    [#6776](https://pulp.plan.io/issues/6776)
-   Ensure that all relations between content models are properly created
    [#6827](https://pulp.plan.io/issues/6827)
-   Auto create repos and distributions for the container push.
    [#6878](https://pulp.plan.io/issues/6878)
-   Fixed not being able to push tags with periods in them.
    [#6884](https://pulp.plan.io/issues/6884)

---

## 1.4.2 (2020-07-13) {: #1.4.2 }

### Bugfixes

-   Improved the performance of the synchronization
    [#6940](https://pulp.plan.io/issues/6940)

---

## 1.4.1 (2020-06-04) {: #1.4.1 }

### Bugfixes

-   Including requirements.txt on MANIFEST.in
    [#6890](https://pulp.plan.io/issues/6890)

---

## 1.4.0 (2020-05-28) {: #1.4.0 }

### Features

-   Enable S3 as alternative storage.
    [#4456](https://pulp.plan.io/issues/4456)

### Bugfixes

-   Fixed webserver snippets config
    [#6628](https://pulp.plan.io/issues/6628)

### Improved Documentation

-   Added a new section about using pull secrets
    [#6315](https://pulp.plan.io/issues/6315)

### Misc

-   [#6733](https://pulp.plan.io/issues/6733), [#6823](https://pulp.plan.io/issues/6823), [#6840](https://pulp.plan.io/issues/6840), [#6842](https://pulp.plan.io/issues/6842)

---

## 1.3.0 (2020-04-23) {: #1.3.0 }

### Features

-   Added support for filtering tags using wildcards
    [#6338](https://pulp.plan.io/issues/6338)

### Misc

-   [#6394](https://pulp.plan.io/issues/6394)

---

## 1.2.0 (2020-03-05) {: #1.2.0 }

### Features

-   Enable users to sync content in mirror mode
    [#5771](https://pulp.plan.io/issues/5771)
-   Provide apache and nginx config snippets to be used by the installer.
    [#6292](https://pulp.plan.io/issues/6292)

### Bugfixes

-   Building an image from a Containerfile no longer requires root access.
    [#5895](https://pulp.plan.io/issues/5895)

### Misc

-   [#6069](https://pulp.plan.io/issues/6069)

---

## 1.1.0 (2020-01-22) {: #1.1.0 }

### Features

-   Let users fetch the list of all distributed repositories via the _catalog endpoint
    [#5772](https://pulp.plan.io/issues/5772)
-   Adds ability to build OCI images from Containerfiles.
    [#5785](https://pulp.plan.io/issues/5785)

### Bugfixes

-   The schema conversion cannot be applied for manifests with foreign layers
    [#5646](https://pulp.plan.io/issues/5646)
-   Adds operation_summaries for ContainerRepository operations
    [#5956](https://pulp.plan.io/issues/5956)

### Misc

-   [#5867](https://pulp.plan.io/issues/5867), [#5907](https://pulp.plan.io/issues/5907)

---

## 1.0.0 (2019-12-12) {: #1.0.0 }

### Features

-   As a user, I can remove all repository container content with ["*"]
    [#5756](https://pulp.plan.io/issues/5756)
-   Enable users to disable the token authentication from the settings
    [#5796](https://pulp.plan.io/issues/5796)
-   As a user I can manage images in OCI format.
    [#5816](https://pulp.plan.io/issues/5816)

### Bugfixes

-   Allow users to provide fully qualified domain name of a token server with an associated port number
    [#5779](https://pulp.plan.io/issues/5779)

### Improved Documentation

-   Add note about access permissions for private and public keys
    [#5778](https://pulp.plan.io/issues/5778)

### Misc

-   [#4592](https://pulp.plan.io/issues/4592), [#5701](https://pulp.plan.io/issues/5701), [#5757](https://pulp.plan.io/issues/5757), [#5780](https://pulp.plan.io/issues/5780), [#5830](https://pulp.plan.io/issues/5830)

---

## 1.0.0rc1 (2019-11-18)

### Features

-   No duplicated content can be present in a repository version.
    [#3541](https://pulp.plan.io/issues/3541)
-   Convert manifests of the format schema 2 to schema 1
    [#4244](https://pulp.plan.io/issues/4244)
-   Add support for pulling content using token authentication
    [#4938](https://pulp.plan.io/issues/4938)
-   Store whitelisted tags in a list instead of CSV string
    [#5515](https://pulp.plan.io/issues/5515)
-   Make repositories "typed". Repositories now live at a detail endpoint. Sync is performed by POSTing to {repo_href}/sync/ remote={remote_href}.
    [#5625](https://pulp.plan.io/issues/5625)
-   Added v2s2 to v2s1 converter.
    [#5635](https://pulp.plan.io/issues/5635)

### Bugfixes

-   Fix using specified proxy for downloads.
    [#5637](https://pulp.plan.io/issues/5637)

### Improved Documentation

-   Change the prefix of Pulp services from pulp-* to pulpcore-*
    [#4554](https://pulp.plan.io/issues/4554)

### Deprecations and Removals

-   Change _type to pulp_type
    [#5454](https://pulp.plan.io/issues/5454)

-   Change _id, _created, _last_updated, _href to pulp_id, pulp_created, pulp_last_updated, pulp_href
    [#5457](https://pulp.plan.io/issues/5457)

-   Remove "_" from _versions_href, _latest_version_href
    [#5548](https://pulp.plan.io/issues/5548)

-   Removing base field: _type .
    [#5550](https://pulp.plan.io/issues/5550)

-   Sync is no longer available at the {remote_href}/sync/ repository={repo_href} endpoint. Instead, use POST {repo_href}/sync/ remote={remote_href}.

    Creating / listing / editing / deleting Container repositories is now performed on /pulp/api/v3/repositories/container/container/ instead of /pulp/api/v3/repositories/.
    Only Container content can be present in a Container repository, and only a Container repository can hold Container content.
    [#5625](https://pulp.plan.io/issues/5625)

### Misc

-   [#3308](https://pulp.plan.io/issues/3308), [#5580](https://pulp.plan.io/issues/5580), [#5690](https://pulp.plan.io/issues/5690)

---

## 0.1.0b7 (2019-10-02)

### Bugfixes

-   Fix a bug that allowed arbitrary url prefixes for custom endpoints.
    [#5486](https://pulp.plan.io/issues/5486)
-   Add Docker-Distribution-API-Version header among response headers.
    [#5527](https://pulp.plan.io/issues/5527)

### Misc

-   [#5470](https://pulp.plan.io/issues/5470)

---

## 0.1.0b6 (2019-09-05)

### Features

-   Add endpoint to recursively copy manifests from a source repository to a destination repository.
    [#3403](https://pulp.plan.io/issues/3403)
-   Add endpoint to recursively add docker content to a repository.
    [#3405](https://pulp.plan.io/issues/3405)
-   As a user I can sync from a docker repo published by Pulp2/Pulp3.
    [#4737](https://pulp.plan.io/issues/4737)
-   Add support for tagging and untagging manifests via an additional endpoint
    [#4934](https://pulp.plan.io/issues/4934)
-   Add endpoint for copying all tags from a source repository, or specific tags by name.
    [#4947](https://pulp.plan.io/issues/4947)
-   Add ability to filter Manifests and ManifestTags by media_type and digest
    [#5033](https://pulp.plan.io/issues/5033)
-   Add ability to filter Manifests, ManifestTags and Blobs by multiple media_types
    [#5157](https://pulp.plan.io/issues/5157)
-   Add endpoint to recursively remove docker content from a repository.
    [#5179](https://pulp.plan.io/issues/5179)

### Bugfixes

-   Allow Accept header to send multiple values.
    [#5211](https://pulp.plan.io/issues/5211)
-   Populate ManifestListManifest thru table during sync.
    [#5235](https://pulp.plan.io/issues/5235)
-   Fixed a problem where repeated syncs created invalid orphaned tags.
    [#5252](https://pulp.plan.io/issues/5252)

### Misc

-   [#4681](https://pulp.plan.io/issues/4681), [#5213](https://pulp.plan.io/issues/5213), [#5218](https://pulp.plan.io/issues/5218)

---

## 0.1.0b5 (2019-07-04)

### Bugfixes

-   Add 'Docker-Content-Digest' header to the response headers.
    [#4646](https://pulp.plan.io/issues/4646)
-   Allow docker remote whitelist_tags to be unset to null.
    [#5017](https://pulp.plan.io/issues/5017)
-   Remove schema1 manifest signature when calculating its digest.
    [#5037](https://pulp.plan.io/issues/5037)

### Improved Documentation

-   Switch to using [towncrier](https://github.com/hawkowl/towncrier) for better release notes.
    [#4875](https://pulp.plan.io/issues/4875)
-   Add an example to the whitelist_tag help text
    [#4994](https://pulp.plan.io/issues/4994)
-   Add list of features to the docker landing page.
    [#5030](https://pulp.plan.io/issues/5030)

### Misc

-   [#4572](https://pulp.plan.io/issues/4572), [#4994](https://pulp.plan.io/issues/4994), [#5014](https://pulp.plan.io/issues/5014)

---

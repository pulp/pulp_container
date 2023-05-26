=========
Changelog
=========

..
    You should *NOT* be adding new change log entries to this file, this
    file is managed by towncrier. You *may* edit previous change logs to
    fix problems like typo corrections or such.
    To add a new change log entry, please see
    https://docs.pulpproject.org/contributing/git.html#changelog-update

    WARNING: Don't drop the next directive!

.. towncrier release notes start

2.15.0 (2023-05-26)
===================


Features
--------

- Added support for automatically creating missing repositories during the import procedure. The
  creation is disabled by default. Use ``create_repositories=True`` to tell Pulp to create missing
  repositories when executing the import procedure.
  `#825 <https://github.com/pulp/pulp_container/issues/825>`__
- Added a check if a manifest already exists locally to decrease the number of downloads from a remote registry when syncing content.
  `#1047 <https://github.com/pulp/pulp_container/issues/1047>`__
- Enhanced push operation efficiency by implementing the utilization of ephemeral blobs and
  manifests, eliminating the need for generating unnecessary repository versions.
  `#1212 <https://github.com/pulp/pulp_container/issues/1212>`__
- Updated compatibility for pulpcore 3.25 and Django 4.2.
  `#1277 <https://github.com/pulp/pulp_container/issues/1277>`__


Bugfixes
--------

- Ensured an HTTP 401 response in case a user provides invalid credentials during the login
  (e.g., via ``podman login``).
  `#918 <https://github.com/pulp/pulp_container/issues/918>`__
- Translated v1 signed schema media_type into v1 schema instead.
  `#1045 <https://github.com/pulp/pulp_container/issues/1045>`__
- Fixed content-disposition header which is used in the object storage backends.
  `#1096 <https://github.com/pulp/pulp_container/issues/1096>`__
- Fixed an issue that caused all staff users to have superuser permissions when accessing the
  registry without token authentication enabled.
  `#1109 <https://github.com/pulp/pulp_container/issues/1109>`__
- Fixed a bug where the Podman client could not verify manifest indices signed with a Pulp signing service.
  `#1135 <https://github.com/pulp/pulp_container/issues/1135>`__
- Fixed a method for determining the media type of manifests when syncing content.
  `#1147 <https://github.com/pulp/pulp_container/issues/1147>`__
- Added application/octet-stream as an accepted media_type for docker config objects.
  `#1156 <https://github.com/pulp/pulp_container/issues/1156>`__
- Fixed signing task that could skip some image signing.
  `#1209 <https://github.com/pulp/pulp_container/issues/1209>`__
- Started triggering only one mount-blob task per upload after back-off.
  `#1211 <https://github.com/pulp/pulp_container/issues/1211>`__
- Started sanitizing input data when creating namespaces or distributions.
  `#1229 <https://github.com/pulp/pulp_container/issues/1229>`__
- Fixed a bug that disallowed users to build images that have artifacts within the same directory.
  `#1234 <https://github.com/pulp/pulp_container/issues/1234>`__
- Fixed a bug that disallowed users to configure custom authentication classes for the token server.
  `#1254 <https://github.com/pulp/pulp_container/issues/1254>`__


Misc
----

- `#1093 <https://github.com/pulp/pulp_container/issues/1093>`__, `#1154 <https://github.com/pulp/pulp_container/issues/1154>`__


----


2.14.5 (2023-04-11)
===================


Bugfixes
--------

- Fixed a bug that disallowed users to configure custom authentication classes for the token server.
  `#1254 <https://github.com/pulp/pulp_container/issues/1254>`__


----


2.14.4 (2023-03-30)
===================


Bugfixes
--------

- Fixed signing task that could skip some image signing.
  `#1209 <https://github.com/pulp/pulp_container/issues/1209>`__
- Relaxed oci manifest json validation to allow other layer mediaTypes than oci layer type.
  `#1227 <https://github.com/pulp/pulp_container/issues/1227>`__


----


2.14.3 (2022-12-02)
===================


Bugfixes
--------

- Fixed a bug where the Podman client could not verify manifest indices signed with a Pulp signing service.
  `#1135 <https://github.com/pulp/pulp_container/issues/1135>`__
- Fixed a method for determining the media type of manifests when syncing content.
  `#1147 <https://github.com/pulp/pulp_container/issues/1147>`__
- Added application/octet-stream as an accepted media_type for docker config objects.
  `#1156 <https://github.com/pulp/pulp_container/issues/1156>`__


----


2.14.2 (2022-10-22)
===================


No significant changes.


----


2.14.1 (2022-10-07)
===================


Bugfixes
--------

- Translated v1 signed schema media_type into v1 schema instead.
  `#1045 <https://github.com/pulp/pulp_container/issues/1045>`__


----


2.14.0 (2022-08-25)
===================


Features
--------

- Added validation for uploaded and synced manifest JSON content.
  `#672 <https://github.com/pulp/pulp_container/issues/672>`__


Bugfixes
--------

- Silenced redundant logs when downloading signatures.
  `#518 <https://github.com/pulp/pulp_container/issues/518>`__
- Silenced redundant GnuPG errors logged while decrypting manifest signatures.
  `#519 <https://github.com/pulp/pulp_container/issues/519>`__
- Fixed a bug that caused untagged manifests to be tagged by their digest during the push operation.
  `#852 <https://github.com/pulp/pulp_container/issues/852>`__
- Fixed internal server errors raised when a podman client (<4.0) used invalid content types for
  manifest lists.
  `#853 <https://github.com/pulp/pulp_container/issues/853>`__
- Fixed a misleading error message raised when a user provided an invalid manifest list.
  `#854 <https://github.com/pulp/pulp_container/issues/854>`__
- Fixed an error that was raised when an OCI manifest did not contain ``mediaType``.
  `#883 <https://github.com/pulp/pulp_container/issues/883>`__
- Started returning an HTTP 401 response in case of invalid credentials provided by a container
  client (e.g., ``podman``).
  `#918 <https://github.com/pulp/pulp_container/issues/918>`__
- Configured aiohttp to avoid rewriting redirect URLs, as some web servers
  (e.g. Amazon CloudFront) can be tempermental about the encoding of the URL.
  `#919 <https://github.com/pulp/pulp_container/issues/919>`__
- Fixed the Content-Length key error raised when uploading images.
  `#921 <https://github.com/pulp/pulp_container/issues/921>`__
- Fixed an HTTP 404 response during sync from registry.redhat.io.
  `#974 <https://github.com/pulp/pulp_container/issues/974>`__
- Introduced the ``pulpcore-manager container-repair-media-type`` command to fix incorrect media
  types of manifests that could have been stored in the database as a result of a sync task.
  `#977 <https://github.com/pulp/pulp_container/issues/977>`__


Misc
----

- `#687 <https://github.com/pulp/pulp_container/issues/687>`__


----


2.13.3 (2022-09-14)
===================


Bugfixes
--------

- Translated v1 signed schema media_type into v1 schema instead.
  `#1045 <https://github.com/pulp/pulp_container/issues/1045>`__


----


2.13.2 (2022-08-24)
===================


Bugfixes
--------

- Fixed an HTTP 404 response during sync from registry.redhat.io.
  `#974 <https://github.com/pulp/pulp_container/issues/974>`__
- Introduced the ``pulpcore-manager container-repair-media-type`` command to fix incorrect media
  types of manifests that could have been stored in the database as a result of a sync task.
  `#977 <https://github.com/pulp/pulp_container/issues/977>`__


----


2.13.1 (2022-08-02)
===================


Bugfixes
--------

- Fixed an error that was raised when an OCI manifest did not contain ``mediaType``.
  `#883 <https://github.com/pulp/pulp_container/issues/883>`__
- Fixed the Content-Length key error raised when uploading images.
  `#921 <https://github.com/pulp/pulp_container/issues/921>`__


----


2.13.0 (2022-06-24)
===================


Features
--------

- Added support for streaming artifacts from object storage.
  `#731 <https://github.com/pulp/pulp_container/issues/731>`__


Bugfixes
--------

- Fixed the machinery for building OCI images.
  `#461 <https://github.com/pulp/pulp_container/issues/461>`__
- Fixed the regular expression for matching base paths in distributions.
  `#756 <https://github.com/pulp/pulp_container/issues/756>`__
- Fixed generation of the redirect url to the object storage
  `#767 <https://github.com/pulp/pulp_container/issues/767>`__
- Enforced the reference to manifests from tags. Note that this bugfix introduces a migration that
  removes tags without any reference to the manifests.
  `#789 <https://github.com/pulp/pulp_container/issues/789>`__
- Improved image upload process from podman/docker clients.
  These clients send data as one big chunk hence we don't need to save it
  as chunk but as an artifact directly.
  `#797 <https://github.com/pulp/pulp_container/issues/797>`__
- Fixed upload does not exist error during image push operation.
  `#861 <https://github.com/pulp/pulp_container/issues/861>`__


Improved Documentation
----------------------

- Improved the documentation for RBAC by adding a new section for roles and a new section for
  migrating from permissions to roles.
  `#641 <https://github.com/pulp/pulp_container/issues/641>`__


Misc
----

- `#678 <https://github.com/pulp/pulp_container/issues/678>`__, `#772 <https://github.com/pulp/pulp_container/issues/772>`__, `#791 <https://github.com/pulp/pulp_container/issues/791>`__, `#809 <https://github.com/pulp/pulp_container/issues/809>`__


----


2.12.3 (2022-08-24)
===================


Bugfixes
--------

- Fixed an error that was raised when an OCI manifest did not contain ``mediaType``.
  `#883 <https://github.com/pulp/pulp_container/issues/883>`__
- Fixed an HTTP 404 response during sync from registry.redhat.io.
  `#974 <https://github.com/pulp/pulp_container/issues/974>`__
- Introduced the ``pulpcore-manager container-repair-media-type`` command to fix incorrect media
  types of manifests that could have been stored in the database as a result of a sync task.
  `#977 <https://github.com/pulp/pulp_container/issues/977>`__


----


2.12.2 (2022-07-11)
===================


Bugfixes
--------

- Fixed upload does not exist error during image push operation.
  `#861 <https://github.com/pulp/pulp_container/issues/861>`__


----


2.12.1 (2022-05-12)
===================


Misc
----

- `#772 <https://github.com/pulp/pulp_container/issues/772>`__


----


2.12.0 (2022-05-05)
===================


Features
--------

- Added more robust validation for unknown fields passed via REST API requests.
  `#475 <https://github.com/pulp/pulp_container/issues/475>`__
- Added validation for signatures' payloads.
  `#512 <https://github.com/pulp/pulp_container/issues/512>`__
- Log messages are now not being translated.
  `#690 <https://github.com/pulp/pulp_container/issues/690>`__


Bugfixes
--------

- Fixed url of the registry root endpoint during signature source check.
  `#646 <https://github.com/pulp/pulp_container/issues/646>`__
- Fixed sync of signed content failing with the error `DeclarativeContent' object has no attribute 'd_content'`.
  `#654 <https://github.com/pulp/pulp_container/issues/654>`__
- Fixed group related creation hooks that failed if no current user could be identified.
  `#673 <https://github.com/pulp/pulp_container/issues/673>`__
- Fixed other instances of fd leak.
  `#679 <https://github.com/pulp/pulp_container/issues/679>`__
- Removed Namespace validation.
  Namespaces are managed transparently on behalf of the user.
  `#688 <https://github.com/pulp/pulp_container/issues/688>`__
- Fixed some tasks that were using /tmp/ instead of the worker working directory.
  `#696 <https://github.com/pulp/pulp_container/issues/696>`__
- Fixed the reference to a serializer for building images.
  `#718 <https://github.com/pulp/pulp_container/issues/718>`__
- Fixed the regular expression for matching dockerhub URLs.
  `#736 <https://github.com/pulp/pulp_container/issues/736>`__


Improved Documentation
----------------------

- Added docs for client signature verification policy.
  `#530 <https://github.com/pulp/pulp_container/issues/530>`__


Misc
----

- `#486 <https://github.com/pulp/pulp_container/issues/486>`__, `#495 <https://github.com/pulp/pulp_container/issues/495>`__, `#606 <https://github.com/pulp/pulp_container/issues/606>`__, `#640 <https://github.com/pulp/pulp_container/issues/640>`__, `#665 <https://github.com/pulp/pulp_container/issues/665>`__


----


2.11.2 (2022-08-24)
===================


Bugfixes
--------

- Fixed an error that was raised when an OCI manifest did not contain ``mediaType``.
  `#883 <https://github.com/pulp/pulp_container/issues/883>`__
- Fixed an HTTP 404 response during sync from registry.redhat.io.
  `#974 <https://github.com/pulp/pulp_container/issues/974>`__
- Introduced the ``pulpcore-manager container-repair-media-type`` command to fix incorrect media
  types of manifests that could have been stored in the database as a result of a sync task.
  `#977 <https://github.com/pulp/pulp_container/issues/977>`__


----


2.11.1 (2022-07-12)
===================


Bugfixes
--------

- Fixed sync of signed content failing with the error `DeclarativeContent' object has no attribute 'd_content'`.
  `#654 <https://github.com/pulp/pulp_container/issues/654>`__
- Fixed group related creation hooks that failed if no current user could be identified.
  `#673 <https://github.com/pulp/pulp_container/issues/673>`__
- Fixed some tasks that were using /tmp/ instead of the worker working directory.
  `#696 <https://github.com/pulp/pulp_container/issues/696>`__
- Fixed upload does not exist error during image push operation.
  `#861 <https://github.com/pulp/pulp_container/issues/861>`__


----


2.11.0 (2022-03-16)
===================


Features
--------

- Allow upload of non-distributable layers.
  `#462 <https://github.com/pulp/pulp_container/issues/462>`__
- Added support for pushing manifest lists via the Registry API.
  `#469 <https://github.com/pulp/pulp_container/issues/469>`__
- Added support for cross repository blob mount.
  `#494 <https://github.com/pulp/pulp_container/issues/494>`__
- Added support for caching responses from the registry. The caching is not enabled by default.
  Enable it by configuring the Redis connection and defining ``CACHE_ENABLED = True`` in the
  settings file.
  `#496 <https://github.com/pulp/pulp_container/issues/496>`__
- Added model, serializer, filter and viewset for image manifest signature.
  Added ability to sync manifest signatures from a sigstore.
  `#498 <https://github.com/pulp/pulp_container/issues/498>`__
- Added ability to sign container images from within The Pulp Registry.
  manifest_signing_service is used to produce signed container content.
  `#500 <https://github.com/pulp/pulp_container/issues/500>`__
- Added support for pushing image signatures to the Pulp Registry. The signatures can be pushed by
  utilizing the extensions API.
  `#502 <https://github.com/pulp/pulp_container/issues/502>`__
- Added an extensions API endpoint for downloading image signatures.
  `#504 <https://github.com/pulp/pulp_container/issues/504>`__
- Enabled users to import/export image signatures.
  `#506 <https://github.com/pulp/pulp_container/issues/506>`__
- Ported RBAC implementation to use pulpcore roles.
  `#508 <https://github.com/pulp/pulp_container/issues/508>`__
- Added recursive removal of manifest signatures when a manifest is removed from a repository.
  `#511 <https://github.com/pulp/pulp_container/issues/511>`__
- Added support for syncing signatures using docker API extension.
  `#528 <https://github.com/pulp/pulp_container/issues/528>`__
- Added ability to remove signatures from a container(push) repo.
  `#548 <https://github.com/pulp/pulp_container/issues/548>`__
- Don't reject manifest that has non-distributable layers during upload.
  `#598 <https://github.com/pulp/pulp_container/issues/598>`__


Bugfixes
--------

- Don't store blob's media_type on the model.
  There is no way to say what mimetype it has when it comes into the registry.
  `#493 <https://github.com/pulp/pulp_container/issues/493>`__
- Account for case when token's scope does not contain type/resource/action.
  `#509 <https://github.com/pulp/pulp_container/issues/509>`__
- Fixed content retrieval from distribution when repo is removed.
  `#513 <https://github.com/pulp/pulp_container/issues/513>`__
- Fixed file descriptor leak during image push.
  `#523 <https://github.com/pulp/pulp_container/issues/523>`__
- Fixed "manifest_id" violates not-null constraint error during sync.
  `#537 <https://github.com/pulp/pulp_container/issues/537>`__
- Fixed error during container image push.
  `#542 <https://github.com/pulp/pulp_container/issues/542>`__
- Return a more concise message exception on 500 during image pull when content is missing on the FS.
  `#555 <https://github.com/pulp/pulp_container/issues/555>`__
- Fixed a bug that disallowed users who were authenticated by a remote webserver to access the
  Registry API endpoints when token authentication was disabled.
  `#558 <https://github.com/pulp/pulp_container/issues/558>`__
- Successfully re-upload artifact in case it was previously removed.
  `#595 <https://github.com/pulp/pulp_container/issues/595>`__
- Fixed check for the signature source location.
  `#617 <https://github.com/pulp/pulp_container/issues/617>`__
- Accept token under access_token for compat reasons.
  `#619 <https://github.com/pulp/pulp_container/issues/619>`__


Misc
----

- `#561 <https://github.com/pulp/pulp_container/issues/561>`__


----


2.10.12 (2023-02-28)
====================


Bugfixes
--------

- Fixed a method for determining the media type of manifests when syncing content.
  `#1147 <https://github.com/pulp/pulp_container/issues/1147>`__


----


2.10.11 (2023-01-11)
====================


Bugfixes
--------

- Fixed container repo sync failure 'null value in column \"image_manifest_id\" violates not-null constraint'.
  `#1190 <https://github.com/pulp/pulp_container/issues/1190>`__


----


2.10.10 (2022-10-20)
====================


Bugfixes
--------

- Fixed a database error raised when creating a distribution with a long base_path.
  `#1103 <https://github.com/pulp/pulp_container/issues/1103>`__


----


2.10.9 (2022-09-14)
===================


Bugfixes
--------

- Translated v1 signed schema media_type into v1 schema instead.
  `#1045 <https://github.com/pulp/pulp_container/issues/1045>`__


----


2.10.8 (2022-08-24)
===================


Bugfixes
--------

- Fixed an HTTP 404 response during sync from registry.redhat.io.
  `#974 <https://github.com/pulp/pulp_container/issues/974>`__
- Introduced the ``pulpcore-manager container-repair-media-type`` command to fix incorrect media
  types of manifests that could have been stored in the database as a result of a sync task.
  `#977 <https://github.com/pulp/pulp_container/issues/977>`__


----


2.10.7 (2022-08-16)
===================


No significant changes.


----


2.10.6 (2022-08-15)
===================


No significant changes.


----


2.10.5 (2022-08-02)
===================


Bugfixes
--------

- Fixed an error that was raised when an OCI manifest did not contain ``mediaType``.
  `#883 <https://github.com/pulp/pulp_container/issues/883>`__


----


2.10.4 (2022-07-11)
===================


Bugfixes
--------

- Fixed upload does not exist error during image push operation.
  `#861 <https://github.com/pulp/pulp_container/issues/861>`__


----


2.10.3 (2022-04-05)
===================


Bugfixes
--------

- Accept token under access_token for compat reasons.
  `#619 <https://github.com/pulp/pulp_container/issues/619>`__
- Fixed group related creation hooks that failed if no current user could be identified.
  `#673 <https://github.com/pulp/pulp_container/issues/673>`__


----


2.10.2 (2022-03-04)
===================


Bugfixes
--------

- Return a more concise message exception on 500 during image pull when content is missing on the FS.
  `#555 <https://github.com/pulp/pulp_container/issues/555>`_
- Successfully re-upload artifact in case it was previously removed.
  `#595 <https://github.com/pulp/pulp_container/issues/595>`_


----


2.10.1 (2022-02-15)
===================


Bugfixes
--------

- Fixed file descriptor leak during image push.
  `#523 <https://github.com/pulp/pulp_container/issues/523>`__
- Fixed "manifest_id" violates not-null constraint error during sync.
  `#537 <https://github.com/pulp/pulp_container/issues/537>`__
- Fixed error during container image push.
  `#542 <https://github.com/pulp/pulp_container/issues/542>`__


----


2.10.0 (2021-12-14)
===================


Features
--------

- Enabled Azure storage backend support.
  `#9488 <https://pulp.plan.io/issues/9488>`_
- Enabled rate_limit option on the remote. Rate limit defines N req/sec per connection.
  `#9607 <https://pulp.plan.io/issues/9607>`_


----


2.9.10 (2023-02-28)
===================


Bugfixes
--------

- Fixed a method for determining the media type of manifests when syncing content.
  `#1147 <https://github.com/pulp/pulp_container/issues/1147>`__
- Fixed container repo sync failure 'null value in column \"image_manifest_id\" violates not-null constraint'.
  `#1190 <https://github.com/pulp/pulp_container/issues/1190>`__


----


2.9.9 (2022-10-20)
==================


Bugfixes
--------

- Fixed a database error raised when creating a distribution with a long base_path.
  `#1103 <https://github.com/pulp/pulp_container/issues/1103>`__


----


2.9.8 (2022-09-14)
==================


Bugfixes
--------

- Translated v1 signed schema media_type into v1 schema instead.
  `#1045 <https://github.com/pulp/pulp_container/issues/1045>`__


----


2.9.7 (2022-08-24)
==================


Bugfixes
--------

- Fixed an HTTP 404 response during sync from registry.redhat.io.
  `#974 <https://github.com/pulp/pulp_container/issues/974>`__
- Introduced the ``pulpcore-manager container-repair-media-type`` command to fix incorrect media
  types of manifests that could have been stored in the database as a result of a sync task.
  `#977 <https://github.com/pulp/pulp_container/issues/977>`__


----


2.9.6 (2022-08-02)
==================


Bugfixes
--------

- Fixed an error that was raised when an OCI manifest did not contain ``mediaType``.
  `#883 <https://github.com/pulp/pulp_container/issues/883>`__


----


2.9.5 (2022-07-11)
==================


Bugfixes
--------

- Accept token under access_token for compat reasons.
  `#619 <https://github.com/pulp/pulp_container/issues/619>`__
- Fixed upload does not exist error during image push operation.
  `#861 <https://github.com/pulp/pulp_container/issues/861>`__


----


2.9.4 (2022-03-04)
===================


Bugfixes
--------

- Return a more concise message exception on 500 during image pull when content is missing on the FS.
  `#555 <https://github.com/pulp/pulp_container/issues/555>`_
- Successfully re-upload artifact in case it was previously removed.
  `#595 <https://github.com/pulp/pulp_container/issues/595>`_


----


2.9.3 (2022-02-15)
==================


Bugfixes
--------

- Fixed file descriptor leak during image push.
  `#523 <https://github.com/pulp/pulp_container/issues/523>`__
- Fixed error during container image push.
  `#542 <https://github.com/pulp/pulp_container/issues/542>`__
- Fixed rate_limit option on the remote. Rate limit defines N req/sec per connection.
  `#578 <https://github.com/pulp/pulp_container/issues/578>`__
- Fixed a bug that caused container clients to be unable to interact with content stored on S3.
  `#579 <https://github.com/pulp/pulp_container/issues/579>`__


----


2.9.2 (2022-02-08)
==================


Bugfixes
--------

- Added validation for the supported manifests and blobs media_types in the push operation.
  `#8303 <https://pulp.plan.io/issues/8303>`_
- Fixed ORM calls in the content app that were made in async context to use sync_to_async.
  `#9454 <https://pulp.plan.io/issues/9454>`_
- Fixed a failure during distribution update that occured when unsetting repository_version.
  `#9497 <https://pulp.plan.io/issues/9497>`_
- Corrected value of ``Content-Length`` header for push upload responses.
  This fixes the *upstream prematurely closed connection while reading upstream* error that would
  appear in nginx logs after a push operation.
  `#9516 <https://pulp.plan.io/issues/9516>`_
- Fixed headers and status codes in the upload/blob responses during image push.
  `#9568 <https://pulp.plan.io/issues/9568>`_
- Send proper blob content_type header when the blob is served.
  `#9571 <https://pulp.plan.io/issues/9571>`_
- Fixed a bug that caused container clients to be unable to interact with content stored on S3.
  `#9586 <https://pulp.plan.io/issues/9586>`_
- Fixed a bug, where permissions were checked against the wrong object type.
  `#9589 <https://pulp.plan.io/issues/9589>`_


Misc
----

- `#9562 <https://pulp.plan.io/issues/9562>`_, `#9618 <https://pulp.plan.io/issues/9618>`_


----


2.9.1 (2021-11-23)
==================


Bugfixes
--------

- Fixed ORM calls in the content app that were made in async context to use sync_to_async.
  (Backported from https://pulp.plan.io/issues/9454).
  `#9538 <https://pulp.plan.io/issues/9538>`_
- Corrected value of ``Content-Length`` header for push upload responses.
  This fixes the *upstream prematurely closed connection while reading upstream* error that would
  appear in nginx logs after a push operation (Backported from https://pulp.plan.io/issues/9516).
  `#9539 <https://pulp.plan.io/issues/9539>`_
- Fixed Azure storage backend support (Backported from https://pulp.plan.io/issues/9488).
  `#9540 <https://pulp.plan.io/issues/9540>`_


----


2.9.0 (2021-10-06)
==================


Bugfixes
--------

- Switched from ``condition`` element to ``condition_expression`` for boolean logic evaluation to
  support latest drf-access-policy.
  `#9092 <https://pulp.plan.io/issues/9092>`_
- Fix OpenAPI schema view
  `#9258 <https://pulp.plan.io/issues/9258>`_
- Refactor sync pipeline to fix a race condition with multiple synchronous syncs.
  `#9292 <https://pulp.plan.io/issues/9292>`_
- Added validation for a repository base path.
  `#9403 <https://pulp.plan.io/issues/9403>`_


Misc
----

- `#9187 <https://pulp.plan.io/issues/9187>`_, `#9203 <https://pulp.plan.io/issues/9203>`_, `#9310 <https://pulp.plan.io/issues/9310>`_, `#9385 <https://pulp.plan.io/issues/9385>`_, `#9466 <https://pulp.plan.io/issues/9466>`_


----


2.8.9 (2022-12-13)
==================


Bugfixes
--------

- Fixed a bug that led Pulp to run out of DB connections during podman pull operations.
  `#1146 <https://github.com/pulp/pulp_container/issues/1146>`__


----


2.8.8 (2022-08-24)
==================


Bugfixes
--------

- Fixed an HTTP 404 response during sync from registry.redhat.io.
  `#974 <https://github.com/pulp/pulp_container/issues/974>`__


----


2.8.7 (2022-04-05)
==================


Bugfixes
--------

- Accept token under access_token for compat reasons.
  `#619 <https://github.com/pulp/pulp_container/issues/619>`__


----


2.8.6 (2022-03-04)
===================


Bugfixes
--------

- Return a more concise message exception on 500 during image pull when content is missing on the FS.
  `#555 <https://github.com/pulp/pulp_container/issues/555>`_
- Successfully re-upload artifact in case it was previously removed.
  `#595 <https://github.com/pulp/pulp_container/issues/595>`_


----


2.8.5 (2022-02-15)
==================


Bugfixes
--------

- Fixed file descriptor leak during image push.
  `#523 <https://github.com/pulp/pulp_container/issues/523>`__
- Fixed error during container image push.
  `#542 <https://github.com/pulp/pulp_container/issues/542>`__


----


2.8.4 (2022-01-27)
==================


Bugfixes
--------

- Fixed "manifest_id" violates not-null constraint error during sync.
  `#537 <https://github.com/pulp/pulp_container/issues/537>`__


----


2.8.3 (2021-12-09)
==================


Bugfixes
--------

- Fixed a bug that caused container clients to be unable to interact with content stored on S3.
  (Backported from https://pulp.plan.io/issues/9586).
  `#9601 <https://pulp.plan.io/issues/9601>`_
- Fixed rate_limit option on the remote which was ignored during the downloads. Rate limit defines
  N req/sec per connection ( backported from https://pulp.plan.io/issues/9610).
  `#9610 <https://pulp.plan.io/issues/9610>`_


----


2.8.2 (2021-11-23)
==================


Bugfixes
--------

- Corrected value of ``Content-Length`` header for push upload responses.
  This fixes the *upstream prematurely closed connection while reading upstream* error that would
  appear in nginx logs after a push operation (Backported from https://pulp.plan.io/issues/9516).
  `#9521 <https://pulp.plan.io/issues/9521>`_
- Fixed ORM calls in the content app that were made in async context to use loop.run_in_executor().
  `#9522 <https://pulp.plan.io/issues/9522>`_
- Fixed Azure storage backend support (Backported from https://pulp.plan.io/issues/9488).
  `#9523 <https://pulp.plan.io/issues/9523>`_
- Added validation for a repository base path (Backported from https://pulp.plan.io/issues/9403).
  `#9526 <https://pulp.plan.io/issues/9526>`_


----


2.8.1 (2021-09-07)
==================


Bugfixes
--------

- Refactor sync pipeline to fix a race condition with multiple synchronous syncs.
  (backported from #9292)
  `#9334 <https://pulp.plan.io/issues/9334>`_


----


2.8.0 (2021-08-04)
==================


Features
--------

- Add model resources to allow pulp import export handle pulp_container content units for synced container repositories.
  `#6636 <https://pulp.plan.io/issues/6636>`_
- Enable reclaim disk space feature for blobs and manifests.This feature is available with pulpcore 3.15+
  `#9169 <https://pulp.plan.io/issues/9169>`_


Bugfixes
--------

- Use proxy auth credentials when syncing content from a Remote.
  `#9065 <https://pulp.plan.io/issues/9065>`_


Deprecations and Removals
-------------------------

- Dropped support for Python 3.6 and 3.7. pulp_container now supports Python 3.8+.
  `#9035 <https://pulp.plan.io/issues/9035>`_


Misc
----

- `#9134 <https://pulp.plan.io/issues/9134>`_


----


2.7.1 (2021-07-21)
==================


Bugfixes
--------

- Use proxy auth credentials when syncing content from a Remote.
  (backported from #9065)
  `#9067 <https://pulp.plan.io/issues/9067>`_


----


2.7.0 (2021-07-01)
==================


Features
--------

- As a user I can update container push repositories.
  `#8313 <https://pulp.plan.io/issues/8313>`_


Bugfixes
--------

- Updated distribution creation policy.
  `#8244 <https://pulp.plan.io/issues/8244>`_
- Improved error logging on failed image push.
  `#8879 <https://pulp.plan.io/issues/8879>`_
- Fixed access policy for the container repository ``repair`` endpoint.
  `#8884 <https://pulp.plan.io/issues/8884>`_


----


2.6.0 (2021-05-20)
==================


Features
--------

- Added ability for users to add a Remote to a Repository that is used by default when syncing.
  `#7795 <https://pulp.plan.io/issues/7795>`_


Bugfixes
--------

- Fixed a bug where image push of the same tag with docker client ended up in the different manifest upload.
  Updated Range header in the blob upload response so it is inclusive.
  `#8543 <https://pulp.plan.io/issues/8543>`_
- Add a fix to prevent server errors on push of new repositories including multiple layers.
  `#8565 <https://pulp.plan.io/issues/8565>`_
- Fixed apache snippet config and removed scheme
  `#8573 <https://pulp.plan.io/issues/8573>`_
- Do not suggest a time to wait on 429 responses. This allows clients to decide to play nice and increase backoff times.
  `#8576 <https://pulp.plan.io/issues/8576>`_
- Fix a bug where users with container.namespace_change_containerdistribution couldn't change distributions.
  `#8618 <https://pulp.plan.io/issues/8618>`_
- Fixed compution of the digest string during the manifest conversion so it also contains the algorithm.
  `#8629 <https://pulp.plan.io/issues/8629>`_
- Create and return empty_blob on the fly.
  `#8631 <https://pulp.plan.io/issues/8631>`_
- Fixed "connection already closed" error in the Registry handler.
  `#8672 <https://pulp.plan.io/issues/8672>`_


Improved Documentation
----------------------

- Fixed broken links to API guide
  `#8125 <https://pulp.plan.io/issues/8125>`_


Misc
----

- `#8581 <https://pulp.plan.io/issues/8581>`_


----


2.5.5 (2022-02-15)
==================


Bugfixes
--------

- Fixed file descriptor leak during image push.
  `#523 <https://pulp.plan.io/issues/523>`__
- Fixed error during container image push.
  `#542 <https://pulp.plan.io/issues/542>`__


----


2.5.4 (2021-12-14)
==================


Bugfixes
--------

- Improved error logging on failed image push. (Backported from https://pulp.plan.io/issues/8879).
  `#8888 <https://pulp.plan.io/issues/8888>`_
- Fixed access policy for the container repository ``repair`` endpoint. (Backported from https://pulp.plan.io/issues/8884).
  `#8889 <https://pulp.plan.io/issues/8889>`_
- Fixed a bug that caused container clients to be unable to interact with content stored on S3.
  (Backported from https://pulp.plan.io/issues/9586).
  `#9600 <https://pulp.plan.io/issues/9600>`_


----


2.5.3 (2021-05-20)
==================


Bugfixes
--------

- Fixed "connection already closed" error in the Registry handler.
  (backported from #8672)
  `#8697 <https://pulp.plan.io/issues/8697>`_
- Fixed compution of the digest string during the manifest conversion so it also contains the algorithm.
  (backported from #8629)
  `#8698 <https://pulp.plan.io/issues/8698>`_
- Create and return empty_blob on the fly.
  (backported from #8631)
  `#8699 <https://pulp.plan.io/issues/8699>`_
- Do not suggest a time to wait on 429 responses. This allows clients to decide to play nice and increase backoff times (Backported from #8576).
  `#8703 <https://pulp.plan.io/issues/8703>`_


----


2.5.2 (2021-04-19)
==================


Bugfixes
--------

- Add a fix to prevent server errors on push of new repositories including multiple layers. (Backported from https://pulp.plan.io/issues/8565)
  `#8591 <https://pulp.plan.io/issues/8591>`_


----


2.5.1 (2021-04-13)
==================


Bugfixes
--------

- Fixed a bug where image push of the same tag with docker client ended up in the different manifest upload.
  Updated Range header in the blob upload response so it is inclusive. (Backported from https://pulp.plan.io/issues/8543)
  `#8545 <https://pulp.plan.io/issues/8545>`_


----


2.5.0 (2021-04-08)
==================


Features
--------

- Updated the catalog endpoint to show only repositories that users have permissions to pull from.
  `#8068 <https://pulp.plan.io/issues/8068>`_
- Config blob is downloaded always, regardless of the remote's settings.
  `#8319 <https://pulp.plan.io/issues/8319>`_


Bugfixes
--------

- Wrapped the repository version creation during blob upload commit in a task that will be waited on by issuing 429.
  `#8151 <https://pulp.plan.io/issues/8151>`_


Improved Documentation
----------------------

- Released container RBAC from tech-preview.
  `#8527 <https://pulp.plan.io/issues/8527>`_


----


2.4.0 (2021-03-18)
==================


Features
--------

- Added pagination to the _catalog and the tags/list endpoint in the registry API.
  `#7974 <https://pulp.plan.io/issues/7974>`_
- Added a fall back to use BasicAuth if TOKEN_AUTH_DISABLED is set.
  `#8074 <https://pulp.plan.io/issues/8074>`_
- Added a new API endpoint that allows users to remove an image by a digest from a push repository.
  `#8105 <https://pulp.plan.io/issues/8105>`_
- Added a `namespace_is_username` helper to decide whether the namespace matches the username of the requests user.
  Changed the namespace access_policy to allow users without permissions to create the namespace that matches their username.
  `#8197 <https://pulp.plan.io/issues/8197>`_


Bugfixes
--------

- Fixed the ``scope`` field returned by the registry when a user was accessing the catalong endpoint without a token. In addition to that, the field ``access`` returned by the token server for the root endpoint was fixed as well.
  `#8045 <https://pulp.plan.io/issues/8045>`_
- Added missing error code that should be returned in the WWW-Authenticate header.
  `#8046 <https://pulp.plan.io/issues/8046>`_
- Fixed a bug that caused the registry to fail during the schema conversion when there was not
  provided the field ``created_by``.
  `#8299 <https://pulp.plan.io/issues/8299>`_
- Prevent the registry pagination classes to fail if a negative page size is requested.
  `#8318 <https://pulp.plan.io/issues/8318>`_


----


2.3.1 (2021-02-15)
==================


Bugfixes
--------

- Use ``get_user_model()`` to prevent pulp_container from crashing when running alongside other pulp plugins that override the default user authentication models.
  `#8260 <https://pulp.plan.io/issues/8260>`_


----


2.3.0 (2021-02-08)
==================


Features
--------

- Added access policy and permission management to container repositories.
  `#7706 <https://pulp.plan.io/issues/7706>`_
- Added access policy and permission management to the container remotes.
  `#7707 <https://pulp.plan.io/issues/7707>`_
- Added access policy for ContainerDistributionViewSet and the Registry API.
  `#7937 <https://pulp.plan.io/issues/7937>`_
- Added access policy and permission management to the container namespaces.
  `#7967 <https://pulp.plan.io/issues/7967>`_
- Added RBAC to the push repository endpoint.
  `#7968 <https://pulp.plan.io/issues/7968>`_
- Add RBAC to the repository version endpoints.
  `#8017 <https://pulp.plan.io/issues/8017>`_
- Made the push and pull permission granting use the ``ContainerDistribution`` access policy.
  `#8075 <https://pulp.plan.io/issues/8075>`_
- Added Owner, Collaborator, and Consumer groups and permissions for Namespaces and Repositories.
  `#8101 <https://pulp.plan.io/issues/8101>`_
- Added a private flag to mark distributions global read accessability.
  `#8102 <https://pulp.plan.io/issues/8102>`_
- Added support for tagging and untagging manifests for push repositories.
  `#8104 <https://pulp.plan.io/issues/8104>`_
- Added RBAC for container content.
  `#8142 <https://pulp.plan.io/issues/8142>`_
- Made the token expiration time configurable via the setting 'TOKEN_EXPIRATION_TIME'.
  `#8147 <https://pulp.plan.io/issues/8147>`_
- Decoupled permissions for registry live api and pulp api.
  `#8153 <https://pulp.plan.io/issues/8153>`_
- Add description field to the ContainerDistribution.
  `#8168 <https://pulp.plan.io/issues/8168>`_


Bugfixes
--------

- Fixed a bug that caused the registry to advertise an invalid digest of a converted manifest.
  `#7923 <https://pulp.plan.io/issues/7923>`_
- Fixed the way how the plugin verifies authenticated users in the token authentication.
  `#8057 <https://pulp.plan.io/issues/8057>`_
- Adjusted the queryset filtering of ``ContainerDistribution`` to include ``private`` and ``Namespace`` permissions.
  `#8206 <https://pulp.plan.io/issues/8206>`_
- Fixed bug experienced when pulling using docker 20.10 client.
  `#8208 <https://pulp.plan.io/issues/8208>`_


Deprecations and Removals
-------------------------

- POST and DELETE requests are no longer available for `/pulp/api/v3/repositories/container/container-push/`.
  Push repositories are still automatically created via docker/podman push and deleted through container distributions.
  `#8014 <https://pulp.plan.io/issues/8014>`_


Misc
----

- `#7936 <https://pulp.plan.io/issues/7936>`_


----


2.2.2 (2021-05-26)
==================


Bugfixes
--------

- Fixed compution of the digest string during the manifest conversion so it also contains the algorithm. (Backported from https://pulp.plan.io/issues/8629).
  `#8818 <https://pulp.plan.io/issues/8818>`_
- Create and return empty_blob on the fly. (Backported from https://pulp.plan.io/issues/8654).
  `#8819 <https://pulp.plan.io/issues/8819>`_
- Fixed "connection already closed" error in the Registry handler. (Backported from https://pulp.plan.io/issues/8672).
  `#8820 <https://pulp.plan.io/issues/8820>`_


----


2.2.1 (2021-03-18)
==================


Bugfixes
--------

- Fixed a bug that caused the registry to fail during the schema conversion when there was not
  provided the field ``created_by``. (Backported from https://pulp.plan.io/issues/8299)
  `#8349 <https://pulp.plan.io/issues/8349>`_
- Fixed a bug that caused the registry to advertise an invalid digest of a converted manifest. (Backported from https://pulp.plan.io/issues/7923)
  `#8350 <https://pulp.plan.io/issues/8350>`_
- Fixed bug experienced when pulling using docker 20.10 client. (Backported from https://pulp.plan.io/issues/8208)
  `#8367 <https://pulp.plan.io/issues/8367>`_


----


2.2.0 (2020-12-09)
==================


Features
--------

- Added namespaces to group repositories and distributions.
  `#7089 <https://pulp.plan.io/issues/7089>`_
- Refactored the registry's push API to not store uploaded chunks in /var/lib/pulp, but rather
  in the shared storage.
  `#7218 <https://pulp.plan.io/issues/7218>`_


Bugfixes
--------

- Fixed the value of registry_path in a container distribution.
  `#7385 <https://pulp.plan.io/issues/7385>`_
- Added validation for tags' names.
  `#7506 <https://pulp.plan.io/issues/7506>`_
- Fixed Renderer to handle properly Manifest and Blob responses.
  `#7620 <https://pulp.plan.io/issues/7620>`_
- Updated models fields to not use settings directly.
  `#7728 <https://pulp.plan.io/issues/7728>`_
- Fixed a bug where Artifacts were missing sha224 checksum after `podman push`.
  `#7774 <https://pulp.plan.io/issues/7774>`_


Improved Documentation
----------------------

- Updated scripts to correctly show the workflows.
  `#7547 <https://pulp.plan.io/issues/7547>`_


Misc
----

- `#7649 <https://pulp.plan.io/issues/7649>`_


----


2.1.3 (2022-05-12)
==================


Misc
----

- `#744 <https://github.com/pulp/pulp_container/issues/744>`_


----


2.1.2 (2021-05-04)
==================


Bugfixes
--------

- Create and return empty_blob on the fly (Backported from https://pulp.plan.io/issues/8631)
  `#8654 <https://pulp.plan.io/issues/8654>`_
- Fixed compution of the digest string during the manifest conversion so it also contains the algorithm (Backported from https://pulp.plan.io/issues/8629).
  `#8655 <https://pulp.plan.io/issues/8655>`_
- Fixed "connection already closed" error in the Registry handler (Backported from https://pulp.plan.io/issues/8672).
  `#8685 <https://pulp.plan.io/issues/8685>`_


----


2.1.1 (2021-03-08)
==================


Bugfixes
--------

- Fixed Renderer to handle properly Manifest and Blob responses. (Backported from https://pulp.plan.io/issues/7620)
  `#8346 <https://pulp.plan.io/issues/8346>`_
- Fixed a bug that caused the registry to advertise an invalid digest of a converted manifest. (Backported from https://pulp.plan.io/issues/7923)
  `#8347 <https://pulp.plan.io/issues/8347>`_
- Fixed a bug that caused the registry to fail during the schema conversion when there was not
  provided the field ``created_by``. (Backported from https://pulp.plan.io/issues/8299)
  `#8348 <https://pulp.plan.io/issues/8348>`_
- Fixed bug experienced when pulling using docker 20.10 client. (Backported from https://pulp.plan.io/issues/8208)
  `#8366 <https://pulp.plan.io/issues/8366>`_


----


2.1.0 (2020-09-23)
==================


Bugfixes
--------

- Fixed the unnecessary double redirect issued for the S3 storage
  `#6826 <https://pulp.plan.io/issues/6826>`_


Improved Documentation
----------------------

- Documented how include/exclude_tags options work with mirror=True/False.
  `#7380 <https://pulp.plan.io/issues/7380>`_


----


2.0.1 (2020-09-08)
==================


Bugfixes
--------

- Fixed bug where users would get 403 response when pulling from the registry running behind an HTTPS
  reverse proxy.
  `#7462 <https://pulp.plan.io/issues/7462>`_


----


2.0.0 (2020-08-18)
====================


Features
--------

- Added 'exclude_tags' to support e.g. skipping source containers in sync.
  `#6922 <https://pulp.plan.io/issues/6922>`_
- Push repositories will be deleted together with their attached distribution.
  `#7172 <https://pulp.plan.io/issues/7172>`_


Bugfixes
--------

- Updated the sync machinery to not store an image manifest as a tag's artifact
  `#6816 <https://pulp.plan.io/issues/6816>`_
- Added a validation, that a push repository cannot be distributed by specifying a version.
  `#7012 <https://pulp.plan.io/issues/7012>`_
- Forbid the REST API methods PATCH and PUT to prevent changes to repositories created via
  docker/podman push requests
  `#7013 <https://pulp.plan.io/issues/7013>`_
- Fixed the rendering of errors in the container registry api.
  `#7054 <https://pulp.plan.io/issues/7054>`_
- Repaired broken registry with TOKEN_AUTH_DISABLED=True
  `#7304 <https://pulp.plan.io/issues/7304>`_


Improved Documentation
----------------------

- Updated docs for 2.0 GA.
  `#7317 <https://pulp.plan.io/issues/7317>`_


Deprecations and Removals
-------------------------

- Renamed 'whitelist_tags' to 'include_tags'.
  `#7070 <https://pulp.plan.io/issues/7070>`_


----


2.0.0b3 (2020-07-16)
====================


Features
--------

- Redirected get on Manifest get to the content app to enable schema conversion.
  Repaired schema conversion to work with django-storage framework.
  `#6824 <https://pulp.plan.io/issues/6824>`_
- Added ContainerPushRepository type to back writeable container registries.
  `#6825 <https://pulp.plan.io/issues/6825>`_
- Added ContentRedirectContentGuard to redirect with preauthenticated urls to the content app.
  `#6894 <https://pulp.plan.io/issues/6894>`_
- Restricted push access to admin user.
  `#6976 <https://pulp.plan.io/issues/6976>`_


Bugfixes
--------

- Refactored token_authentication that now happens in pulpcore-api app
  `#6894 <https://pulp.plan.io/issues/6894>`_
- Fixed a crash when trying to access content with an unparseable token.
  `#7124 <https://pulp.plan.io/issues/7124>`_
- Fixed a runtime error which was triggered when a registry client sends an accept header with an
  inappropriate media type for a manifest and the conversion failed.
  `#7125 <https://pulp.plan.io/issues/7125>`_


Misc
----

- `#5302 <https://pulp.plan.io/issues/5302>`_


----


2.0.0b2 (2020-06-08)
====================


Bugfixes
--------

- Fixed the client_max_body_size value in the nginx config.
  `#6916 <https://pulp.plan.io/issues/6916>`_


----


2.0.0b1 (2020-06-03)
====================


Features
--------

- Added REST APIs for handling docker/podman push.
  `#5027 <https://pulp.plan.io/issues/5027>`_

Bugfixes
--------

- Fixed 500 error when pulling by tag.
  `#6776 <https://pulp.plan.io/issues/6776>`_
- Ensure that all relations between content models are properly created
  `#6827 <https://pulp.plan.io/issues/6827>`_
- Auto create repos and distributions for the container push.
  `#6878 <https://pulp.plan.io/issues/6878>`_
- Fixed not being able to push tags with periods in them.
  `#6884 <https://pulp.plan.io/issues/6884>`_


----


1.4.2 (2020-07-13)
==================

Bugfixes
--------

- Improved the performance of the synchronization
  `#6940 <https://pulp.plan.io/issues/6940>`_


----


1.4.1 (2020-06-04)
==================


Bugfixes
--------

- Including requirements.txt on MANIFEST.in
  `#6890 <https://pulp.plan.io/issues/6890>`_


----


1.4.0 (2020-05-28)
==================


Features
--------

- Enable S3 as alternative storage.
  `#4456 <https://pulp.plan.io/issues/4456>`_


Bugfixes
--------

- Fixed webserver snippets config
  `#6628 <https://pulp.plan.io/issues/6628>`_


Improved Documentation
----------------------

- Added a new section about using pull secrets
  `#6315 <https://pulp.plan.io/issues/6315>`_


Misc
----

- `#6733 <https://pulp.plan.io/issues/6733>`_, `#6823 <https://pulp.plan.io/issues/6823>`_, `#6840 <https://pulp.plan.io/issues/6840>`_, `#6842 <https://pulp.plan.io/issues/6842>`_


----


1.3.0 (2020-04-23)
==================


Features
--------

- Added support for filtering tags using wildcards
  `#6338 <https://pulp.plan.io/issues/6338>`_


Misc
----

- `#6394 <https://pulp.plan.io/issues/6394>`_


----


1.2.0 (2020-03-05)
==================


Features
--------

- Enable users to sync content in mirror mode
  `#5771 <https://pulp.plan.io/issues/5771>`_
- Provide apache and nginx config snippets to be used by the installer.
  `#6292 <https://pulp.plan.io/issues/6292>`_


Bugfixes
--------

- Building an image from a Containerfile no longer requires root access.
  `#5895 <https://pulp.plan.io/issues/5895>`_


Misc
----

- `#6069 <https://pulp.plan.io/issues/6069>`_


----


1.1.0 (2020-01-22)
==================


Features
--------

- Let users fetch the list of all distributed repositories via the _catalog endpoint
  `#5772 <https://pulp.plan.io/issues/5772>`_
- Adds ability to build OCI images from Containerfiles.
  `#5785 <https://pulp.plan.io/issues/5785>`_


Bugfixes
--------

- The schema conversion cannot be applied for manifests with foreign layers
  `#5646 <https://pulp.plan.io/issues/5646>`_
- Adds operation_summaries for ContainerRepository operations
  `#5956 <https://pulp.plan.io/issues/5956>`_


Misc
----

- `#5867 <https://pulp.plan.io/issues/5867>`_, `#5907 <https://pulp.plan.io/issues/5907>`_


----


1.0.0 (2019-12-12)
==================


Features
--------

- As a user, I can remove all repository container content with ["*"]
  `#5756 <https://pulp.plan.io/issues/5756>`_
- Enable users to disable the token authentication from the settings
  `#5796 <https://pulp.plan.io/issues/5796>`_
- As a user I can manage images in OCI format.
  `#5816 <https://pulp.plan.io/issues/5816>`_


Bugfixes
--------

- Allow users to provide fully qualified domain name of a token server with an associated port number
  `#5779 <https://pulp.plan.io/issues/5779>`_


Improved Documentation
----------------------

- Add note about access permissions for private and public keys
  `#5778 <https://pulp.plan.io/issues/5778>`_


Misc
----

- `#4592 <https://pulp.plan.io/issues/4592>`_, `#5701 <https://pulp.plan.io/issues/5701>`_, `#5757 <https://pulp.plan.io/issues/5757>`_, `#5780 <https://pulp.plan.io/issues/5780>`_, `#5830 <https://pulp.plan.io/issues/5830>`_


----


1.0.0rc1 (2019-11-18)
=====================


Features
--------

- No duplicated content can be present in a repository version.
  `#3541 <https://pulp.plan.io/issues/3541>`_
- Convert manifests of the format schema 2 to schema 1
  `#4244 <https://pulp.plan.io/issues/4244>`_
- Add support for pulling content using token authentication
  `#4938 <https://pulp.plan.io/issues/4938>`_
- Store whitelisted tags in a list instead of CSV string
  `#5515 <https://pulp.plan.io/issues/5515>`_
- Make repositories "typed". Repositories now live at a detail endpoint. Sync is performed by POSTing to {repo_href}/sync/ remote={remote_href}.
  `#5625 <https://pulp.plan.io/issues/5625>`_
- Added v2s2 to v2s1 converter.
  `#5635 <https://pulp.plan.io/issues/5635>`_


Bugfixes
--------

- Fix using specified proxy for downloads.
  `#5637 <https://pulp.plan.io/issues/5637>`_


Improved Documentation
----------------------

- Change the prefix of Pulp services from pulp-* to pulpcore-*
  `#4554 <https://pulp.plan.io/issues/4554>`_


Deprecations and Removals
-------------------------

- Change `_type` to `pulp_type`
  `#5454 <https://pulp.plan.io/issues/5454>`_
- Change `_id`, `_created`, `_last_updated`, `_href` to `pulp_id`, `pulp_created`, `pulp_last_updated`, `pulp_href`
  `#5457 <https://pulp.plan.io/issues/5457>`_
- Remove "_" from `_versions_href`, `_latest_version_href`
  `#5548 <https://pulp.plan.io/issues/5548>`_
- Removing base field: `_type` .
  `#5550 <https://pulp.plan.io/issues/5550>`_
- Sync is no longer available at the {remote_href}/sync/ repository={repo_href} endpoint. Instead, use POST {repo_href}/sync/ remote={remote_href}.

  Creating / listing / editing / deleting Container repositories is now performed on /pulp/api/v3/repositories/container/container/ instead of /pulp/api/v3/repositories/.
  Only Container content can be present in a Container repository, and only a Container repository can hold Container content.
  `#5625 <https://pulp.plan.io/issues/5625>`_


Misc
----

- `#3308 <https://pulp.plan.io/issues/3308>`_, `#5580 <https://pulp.plan.io/issues/5580>`_, `#5690 <https://pulp.plan.io/issues/5690>`_


----


4.0.0b7 (2019-10-02)
====================


Bugfixes
--------

- Fix a bug that allowed arbitrary url prefixes for custom endpoints.
  `#5486 <https://pulp.plan.io/issues/5486>`_
- Add Docker-Distribution-API-Version header among response headers.
  `#5527 <https://pulp.plan.io/issues/5527>`_


Misc
----

- `#5470 <https://pulp.plan.io/issues/5470>`_


----


4.0.0b6 (2019-09-05)
====================


Features
--------

- Add endpoint to recursively copy manifests from a source repository to a destination repository.
  `#3403 <https://pulp.plan.io/issues/3403>`_
- Add endpoint to recursively add docker content to a repository.
  `#3405 <https://pulp.plan.io/issues/3405>`_
- As a user I can sync from a docker repo published by Pulp2/Pulp3.
  `#4737 <https://pulp.plan.io/issues/4737>`_
- Add support for tagging and untagging manifests via an additional endpoint
  `#4934 <https://pulp.plan.io/issues/4934>`_
- Add endpoint for copying all tags from a source repository, or specific tags by name.
  `#4947 <https://pulp.plan.io/issues/4947>`_
- Add ability to filter Manifests and ManifestTags by media_type and digest
  `#5033 <https://pulp.plan.io/issues/5033>`_
- Add ability to filter Manifests, ManifestTags and Blobs by multiple media_types
  `#5157 <https://pulp.plan.io/issues/5157>`_
- Add endpoint to recursively remove docker content from a repository.
  `#5179 <https://pulp.plan.io/issues/5179>`_


Bugfixes
--------

- Allow Accept header to send multiple values.
  `#5211 <https://pulp.plan.io/issues/5211>`_
- Populate ManifestListManifest thru table during sync.
  `#5235 <https://pulp.plan.io/issues/5235>`_
- Fixed a problem where repeated syncs created invalid orphaned tags.
  `#5252 <https://pulp.plan.io/issues/5252>`_


Misc
----

- `#4681 <https://pulp.plan.io/issues/4681>`_, `#5213 <https://pulp.plan.io/issues/5213>`_, `#5218 <https://pulp.plan.io/issues/5218>`_


----


4.0.0b5 (2019-07-04)
====================


Bugfixes
--------

- Add 'Docker-Content-Digest' header to the response headers.
  `#4646 <https://pulp.plan.io/issues/4646>`_
- Allow docker remote whitelist_tags to be unset to null.
  `#5017 <https://pulp.plan.io/issues/5017>`_
- Remove schema1 manifest signature when calculating its digest.
  `#5037 <https://pulp.plan.io/issues/5037>`_


Improved Documentation
----------------------

- Switch to using `towncrier <https://github.com/hawkowl/towncrier>`_ for better release notes.
  `#4875 <https://pulp.plan.io/issues/4875>`_
- Add an example to the whitelist_tag help text
  `#4994 <https://pulp.plan.io/issues/4994>`_
- Add list of features to the docker landing page.
  `#5030 <https://pulp.plan.io/issues/5030>`_


Misc
----

- `#4572 <https://pulp.plan.io/issues/4572>`_, `#4994 <https://pulp.plan.io/issues/4994>`_, `#5014 <https://pulp.plan.io/issues/5014>`_


----

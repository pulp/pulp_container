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

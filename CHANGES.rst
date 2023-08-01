=========
Changelog
=========

..
    You should *NOT* be adding new change log entries to this file, this
    file is managed by towncrier. You *may* edit previous change logs to
    fix problems like typo corrections or such.
    To add a new change log entry, please see
    https://docs.pulpproject.org/en/3.0/nightly/contributing/git.html#changelog-update

    WARNING: Don't drop the next directive!

.. towncrier release notes start

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


0.1.0b7 (2019-10-02)
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


0.1.0b6 (2019-09-05)
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


0.1.0b5 (2019-07-04)
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

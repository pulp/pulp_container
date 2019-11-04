.. _content-management:

Manage Docker Content in a Repository
=====================================

There are multiple ways that users can manage Docker content in repositories:

   1. :ref:`Tag<tagging-workflow>` or :ref:`Untag<untagging-workflow>` Manifests in a repository.
   2. Recursively :ref:`add<recursive-add>` or :ref:`remove<recursive-remove>` Docker content.
   3. Copy :ref:`tags<tag-copy>` or :ref:`manifests <manifest-copy>` from source repository.

.. warning::

   Users **can but probably should not not** add and remove Docker
   content directly using the `repository version create endpoint
   <https://docs.pulpproject.org/en/3.0/nightly/restapi.html#operation/repositories_versions_create>`_.
   This endpoint should be reserved for advanced usage and is considered
   **unsafe** for Docker content, because it is not recursive and it
   allows users to create **corrupted repositories**.

Each of these workflows kicks off a task, and when the task is complete,
a new repository version will have been created.

.. _tagging-workflow:

Tagging
-------

Images are described by manifests. The procedure of an image tagging is
related to manifests because of that. In pulp, it is required to specify
a digest of a manifest in order to create a tag for the corresponding
image.

Below is provided an example on how to tag an image within a repository.
First, a digest of an existing manifest is selected. Then, a custom tag is
applied to the corresponding manifest.

.. literalinclude:: ../_scripts/image_tagging.sh
   :language: bash

A new distribution can be created to include the newly created tag. This
allows clients to pull the image with the applied tag.

.. literalinclude:: ../_scripts/download_after_tagging.sh
    :language: bash

Each tag has to be unique within a repository to prevent ambiguity. When
a user is trying to tag an image with a same name but with a different
digest, the tag associated with the old manifest is going to be
eliminated in a new repository version. Note that a tagging of same
images with existing names still creates a new repository version.

Reference: `Docker Tagging Usage <../restapi.html#tag/docker:-tag>`_

.. _untagging-workflow:

Untagging
---------

An untagging is an inverse operation to the tagging. To remove a tag
applied to an image, it is required to issue the following calls.

.. literalinclude:: ../_scripts/image_untagging.sh
    :language: bash

Pulp will create a new repository version which will not contain the
corresponding tag. The removed tag however still persists in a database.
When a client tries to untag an image that was already untagged, a new
repository version is created as well.

Reference: `Docker Untagging Usage <../restapi.html#tag/docker:-untag>`_

.. _recursive-add:

Recursively Add Content to a Repository
---------------------------------------

Any Docker content can be added to a repository version with the
recursive-add endpoint. Here, "recursive" means that the content will be
added, as well as all related content.


.. _docker-content-relations:

Relations:
   - Adding a **tag**  will also add the tagged manifest and its related
     content.
   - Adding a **manifest** (manifest list) will also add related
     manifests and their related content.
   - Adding a **manifest** (not manifest list) will also add related
     blobs.

.. note::
   Because tag names are unique within a repository version, adding a tag
   with a duplicate name will first remove the existing tag
   (non-recursively).

Begin by following the :ref:`Synchronize <sync-workflow>` workflow to
start with a repository that has some content in it.

Next create a new repository that we can add content to.

.. literalinclude:: ../_scripts/destination_repo.sh
   :language: bash

Now we recursively add a tag to the destination repository.

.. literalinclude:: ../_scripts/recursive_add_tag.sh
   :language: bash

We have added our single tag, as well as the content necessary for that
tag to function correctly when pulled by a client.

New Repository Version::

   {
       "pulp_created": "2019-09-05T19:04:06.152589Z",
       "pulp_href": "/pulp/api/v3/repositories/docker/docker/ce642635-dd9b-423f-82c4-86a150b9f5fe/versions/10/",
       "base_version": null,
       "content_summary": {
           "added": {
               "docker.tag": {
                   "count": 1,
                   "href": "/pulp/api/v3/content/docker/tags/?repository_version_added=/pulp/api/v3/repositories/docker/docker/ce642635-dd9b-423f-82c4-86a150b9f5fe/versions/10/"
               }
           },
           "present": {
               "docker.blob": {
                   "count": 20,
                   "href": "/pulp/api/v3/content/docker/blobs/?repository_version=/pulp/api/v3/repositories/docker/docker/ce642635-dd9b-423f-82c4-86a150b9f5fe/versions/10/"
               },
               "docker.manifest": {
                   "count": 10,
                   "href": "/pulp/api/v3/content/docker/manifests/?repository_version=/pulp/api/v3/repositories/docker/docker/ce642635-dd9b-423f-82c4-86a150b9f5fe/versions/10/"
               },
               "docker.tag": {
                   "count": 1,
                   "href": "/pulp/api/v3/content/docker/tags/?repository_version=/pulp/api/v3/repositories/docker/docker/ce642635-dd9b-423f-82c4-86a150b9f5fe/versions/10/"
               }
           },
           "removed": {
               "docker.tag": {
                   "count": 1,
                   "href": "/pulp/api/v3/content/docker/tags/?repository_version_removed=/pulp/api/v3/repositories/docker/docker/ce642635-dd9b-423f-82c4-86a150b9f5fe/versions/10/"
               }
           }
       },
       "number": 10
   }

.. note::

   Directly adding a manifest that happens to be tagged in another repo
   will **not** include its tags.

Reference: `Docker Recursive Add Usage <../restapi.html#tag/docker:-recursive-add>`_

.. _recursive-remove:

Recursively Remove Content from a Repository
--------------------------------------------

Any Docker content can be removed from a repository version with the
recursive-remove endpoint. Recursive remove is symmetrical with
recursive add, meaning that performing a recursive-add and a
recursive-remove back-to-back with the same content will result in the
original content set. If other operations (i.e. tagging) are done between
recursive-add and recursive remove, they can break the symmetry.

Removing a tag also removes the tagged_manifest and its related content,
which is **new behavior with Pulp 3**. If you just want to remove the
tag, but not the related content, use the :ref:`untagging
workflow<untagging-workflow>`.


Recursive remove **does not** remove content that is related to content
that will stay in the repository. For example, if a manifest is tagged,
the manifest cannot be removed from the repository-- instead the tag
should be removed.

See :ref:`relations<docker-content-relations>`

Continuing from the :ref:`recursive add workflow<recursive-add>`, we can
remove the tag and the related content that is no longer needed.

.. literalinclude:: ../_scripts/recursive_remove_tag.sh
   :language: bash

Now we can see that the tag and related content that was added has now
been removed, resulting in an empty repository.

New Repository Version::

      {
          "pulp_created": "2019-09-10T13:25:44.078017Z",
          "pulp_href": "/pulp/api/v3/repositories/docker/docker/c2f67416-7200-4dcc-9868-f320431aae20/versions/2/",
          "base_version": null,
          "content_summary": {
              "added": {},
              "present": {},
              "removed": {
                  "docker.blob": {
                      "count": 20,
                      "href": "/pulp/api/v3/content/docker/blobs/?repository_version_removed=/pulp/api/v3/repositories/docker/docker/c2f67416-7200-4dcc-9868-f320431aae20/versions/2/"
                  },
                  "docker.manifest": {
                      "count": 10,
                      "href": "/pulp/api/v3/content/docker/manifests/?repository_version_removed=/pulp/api/v3/repositories/docker/docker/c2f67416-7200-4dcc-9868-f320431aae20/versions/2/"
                  },
                  "docker.tag": {
                      "count": 1,
                      "href": "/pulp/api/v3/content/docker/tags/?repository_version_removed=/pulp/api/v3/repositories/docker/docker/c2f67416-7200-4dcc-9868-f320431aae20/versions/2/"
                  }
              }
          },
          "number": 2
      }

Reference: `Docker Recursive Remove Usage <../restapi.html#tag/docker:-recursive-remove>`_

.. _tag-copy:

Recursively Copy Tags from a Source Repository
----------------------------------------------

Tags in one repository can be copied to another repository using the tag
copy endpoint.

When no names are specified, all tags are recursively copied. If names are
specified, only the matching tags are recursively copied.

If tag names being copied already exist in the destination repository,
the conflicting tags are removed from the destination repository and the
new tags are added. This action is not recursive, no manifests or blobs
are removed.

Again we start with a new destination repository.

.. literalinclude:: ../_scripts/destination_repo.sh
   :language: bash

With copy (contrasted to recursive add) we do not need to retrieve the
href of the tag. Rather, we can specify the tag by source repository and
name.

.. literalinclude:: ../_scripts/tag_copy.sh
   :language: bash

New Repository Version::

   {
       "pulp_created": "2019-09-10T13:42:12.572859Z",
       "pulp_href": "/pulp/api/v3/repositories/docker/docker/2b1c6d76-c369-4f31-8eb8-9d5d92bb2346/versions/1/",
       "base_version": null,
       "content_summary": {
           "added": {
               "docker.blob": {
                   "count": 20,
                   "href": "/pulp/api/v3/content/docker/blobs/?repository_version_added=/pulp/api/v3/repositories/docker/docker/2b1c6d76-c369-4f31-8eb8-9d5d92bb2346/versions/1/"
               },
               "docker.manifest": {
                   "count": 10,
                   "href": "/pulp/api/v3/content/docker/manifests/?repository_version_added=/pulp/api/v3/repositories/docker/docker/2b1c6d76-c369-4f31-8eb8-9d5d92bb2346/versions/1/"
               },
               "docker.tag": {
                   "count": 1,
                   "href": "/pulp/api/v3/content/docker/tags/?repository_version_added=/pulp/api/v3/repositories/docker/docker/2b1c6d76-c369-4f31-8eb8-9d5d92bb2346/versions/1/"
               }
           },
           "present": {
               "docker.blob": {
                   "count": 20,
                   "href": "/pulp/api/v3/content/docker/blobs/?repository_version=/pulp/api/v3/repositories/docker/docker/2b1c6d76-c369-4f31-8eb8-9d5d92bb2346/versions/1/"
               },
               "docker.manifest": {
                   "count": 10,
                   "href": "/pulp/api/v3/content/docker/manifests/?repository_version=/pulp/api/v3/repositories/docker/docker/2b1c6d76-c369-4f31-8eb8-9d5d92bb2346/versions/1/"
               },
               "docker.tag": {
                   "count": 1,
                   "href": "/pulp/api/v3/content/docker/tags/?repository_version=/pulp/api/v3/repositories/docker/docker/2b1c6d76-c369-4f31-8eb8-9d5d92bb2346/versions/1/"
               }
           },
           "removed": {}
       },
       "number": 1
   }

Reference: `Docker Copy Tags Usage <../restapi.html#operation/docker_tags_copy_create>`_

.. _manifest-copy:

Recursively Copy Manifests from a Source Repository
---------------------------------------------------

Manifests in one repository can be copied to another repository using
the manifest copy endpoint.

If digests are specified, only the manifests (and their recursively
related content) will be added.

If media_types are specified, only manifests matching that media type
(and their recursively related content) will be added. This allows users
to copy only manifest lists, for example.

.. literalinclude:: ../_scripts/manifest_copy.sh
   :language: bash

New Repository Version::

   {
       "pulp_created": "2019-09-20T13:53:04.907351Z",
       "pulp_href": "/pulp/api/v3/repositories/docker/docker/70450dfb-ae46-4061-84e3-97eb71cf9414/versions/2/",
       "base_version": null,
       "content_summary": {
           "added": {
               "docker.blob": {
                   "count": 31,
                   "href": "/pulp/api/v3/content/docker/blobs/?repository_version_added=/pulp/api/v3/repositories/docker/docker/70450dfb-ae46-4061-84e3-97eb71cf9414/versions/2/"
               },
               "docker.manifest": {
                   "count": 21,
                   "href": "/pulp/api/v3/content/docker/manifests/?repository_version_added=/pulp/api/v3/repositories/docker/docker/70450dfb-ae46-4061-84e3-97eb71cf9414/versions/2/"
               }
           },
           "present": {
               "docker.blob": {
                   "count": 31,
                   "href": "/pulp/api/v3/content/docker/blobs/?repository_version=/pulp/api/v3/repositories/docker/docker/4061-84e3-97eb71cf9414/versions/2/"
               },
               "docker.manifest": {
                   "count": 21,
                   "href": "/pulp/api/v3/content/docker/manifests/?repository_version=/pulp/api/v3/repositories/docker/docker/4061-84e3-97eb71cf9414/versions/2/"
               }
           },
           "removed": {}
       },
       "number": 2
   }

Reference: `Docker Copy Manifests Usage <../restapi.html#operation/docker_manifests_copy_create>`_

# Manage Images

There are multiple ways that users can manage Container content in repositories:

1. [Tag](#tagging) or [Untag](#untagging) Manifests in a repository.
2. Recursively [Add Content](#add-content) or [Remove Content](#remove-content) container content.
3. [Copy Tags](#copy-tags) or [Copy Manifests](#copy-manifests) from source repository.

Each of these workflows kicks off a task, and when the task is complete,
a new repository version will have been created.


## Tagging

Images are described by manifests. The procedure of an image tagging is
related to manifests because of that. In pulp, it is required to specify
a digest of a manifest in order to create a tag for the corresponding
image.

Below is provided an example on how to tag an image within a repository.
First, a digest of an existing manifest is selected. Then, a custom tag is
applied to the corresponding manifest.

```bash
TAG_NAME='custom_tag'
MANIFEST_DIGEST=$(http $BASE_ADDR'/pulp/api/v3/content/container/manifests/?repository_version='$REPOVERSION_HREF \
  | jq -r '.results | first | .digest')

echo "Tagging the manifest."
pulp container repository tag --name test --tag $TAG_NAME --digest $MANIFEST_DIGEST
```

A new distribution can be created to include the newly created tag. This
allows clients to pull the image with the applied tag.

```bash
TAG_NAME='custom_tag'

DIST_NAME=$(head /dev/urandom | tr -dc a-z | head -c5)
DIST_BASE_PATH='tag'

echo "Publishing the latest repository."
DISTRIBUTION_HREF=$(pulp container distribution create --name $DIST_NAME --base-path $DIST_BASE_PATH --repository $REPO_HREF \
jq -r '.pulp_href')
REGISTRY_PATH=$(http $BASE_ADDR$DISTRIBUTION_HREF \
  | jq -r '.registry_path')

echo "Running ${REGISTRY_PATH}:${TAG_NAME}."
sudo docker login -u admin -p password $REGISTRY_PATH
sudo docker run $REGISTRY_PATH:$TAG_NAME
```

Each tag has to be unique within a repository to prevent ambiguity. When
a user is trying to tag an image with a same name but with a different
digest, the tag associated with the old manifest is going to be
eliminated in a new repository version.


## Untagging

An untagging is an inverse operation to the tagging. To remove a tag
applied to an image, it is required to issue the following calls.

```bash
pulp container repository untag --name test --tag $TAG_NAME
```

Pulp will create a new repository version which will not contain the
corresponding tag. The removed tag however still persists in a database.
When a client tries to untag an image that was already untagged, a new
repository version is created as well.

## Add Content

Any Container content can be added to a repository version with the
recursive-add endpoint. Here, "recursive" means that the content will be
added, as well as all related content.

Relations:
 - Adding a **tag**  will also add the tagged manifest and its related
    content.
  - Adding a **manifest** (manifest list) will also add related
    manifests and their related content.
  - Adding a **manifest** (not manifest list) will also add related
    blobs.

!!! note

    Because tag names are unique within a repository version, adding a tag
    with a duplicate name will first remove the existing tag
    (non-recursively).


Begin by following the `Synchronize <sync-workflow>` workflow to
start with a repository that has some content in it.

Next create a new repository that we can add content to.

```bash
SECOND_REPO_HREF=$(pulp container repository create --name second | jq -r ".pulp_href")
```

Now we recursively add a tag to the destination repository.

```bash
echo "Retrieve the href of Tag manifest_a in the synced repository."
TAG_HREF=$(http $BASE_ADDR'/pulp/api/v3/content/container/tags/?repository_version='$REPOVERSION_HREF'&name=manifest_a' \
  | jq -r '.results | first | .pulp_href')

echo "Create a task to recursively add a tag to the repo."
TASK_HREF=$(http POST $BASE_ADDR$SECOND_REPO_HREF'add/' \
  content_units:="[\"$TAG_HREF\"]" \
  | jq -r '.task')
```

We have added our single tag, as well as the content necessary for that
tag to function correctly when pulled by a client.

New Repository Version:

```
{
    "pulp_created": "2019-09-05T19:04:06.152589Z",
    "pulp_href": "/pulp/api/v3/repositories/container/container/ce642635-dd9b-423f-82c4-86a150b9f5fe/versions/10/",
    "base_version": null,
    "content_summary": {
        "added": {
            "container.tag": {
                "count": 1,
                "href": "/pulp/api/v3/content/container/tags/?repository_version_added=/pulp/api/v3/repositories/container/container/ce642635-dd9b-423f-82c4-86a150b9f5fe/versions/10/"
            }
        },
        "present": {
            "container.blob": {
                "count": 20,
                "href": "/pulp/api/v3/content/container/blobs/?repository_version=/pulp/api/v3/repositories/container/container/ce642635-dd9b-423f-82c4-86a150b9f5fe/versions/10/"
            },
            "container.manifest": {
                "count": 10,
                "href": "/pulp/api/v3/content/container/manifests/?repository_version=/pulp/api/v3/repositories/container/container/ce642635-dd9b-423f-82c4-86a150b9f5fe/versions/10/"
            },
            "container.tag": {
                "count": 1,
                "href": "/pulp/api/v3/content/container/tags/?repository_version=/pulp/api/v3/repositories/container/container/ce642635-dd9b-423f-82c4-86a150b9f5fe/versions/10/"
            }
        },
        "removed": {
            "container.tag": {
                "count": 1,
                "href": "/pulp/api/v3/content/container/tags/?repository_version_removed=/pulp/api/v3/repositories/container/container/ce642635-dd9b-423f-82c4-86a150b9f5fe/versions/10/"
            }
        }
    },
    "number": 10
}
```

!!! note

    Directly adding a manifest that happens to be tagged in another repo
    will **not** include its tags.



## Remove Content

Any Container content can be removed from a repository version with the
recursive-remove endpoint. Recursive remove is symmetrical with
recursive add, meaning that performing a recursive-add and a
recursive-remove back-to-back with the same content will result in the
original content set. If other operations (i.e. tagging) are done between
recursive-add and recursive remove, they can break the symmetry.

Removing a tag also removes the tagged manifest and its related content,
which is **new behavior with Pulp 3**. If you just want to remove the
tag, but not the related content, use the [untagging workflow](#untagging).

Recursive remove **does not** remove content that is related to content
that will stay in the repository. For example, if a manifest is tagged,
the manifest cannot be removed from the repository -- instead the tag
should be removed. See the relations noted in the [Add Content](#add-content) section.

Continuing from the recursive add workflow, we can
remove the tag and the related content that is no longer needed.

```bash
echo "Create a task to recursively remove the same tag to the repo."
TASK_HREF=$(http POST $BASE_ADDR$SECOND_REPO_HREF'remove/' \
  content_units:="[\"$TAG_HREF\"]" \
  | jq -r '.task')
```

!!! note

    Users can remove all content from the repo by specifying '\*' in the content units field.

Now we can see that the tag and related content that was added has now
been removed, resulting in an empty repository.

New Repository Version:

```
{
    "pulp_created": "2019-09-10T13:25:44.078017Z",
    "pulp_href": "/pulp/api/v3/repositories/container/container/c2f67416-7200-4dcc-9868-f320431aae20/versions/2/",
    "base_version": null,
    "content_summary": {
        "added": {},
        "present": {},
        "removed": {
            "container.blob": {
                "count": 20,
                "href": "/pulp/api/v3/content/container/blobs/?repository_version_removed=/pulp/api/v3/repositories/container/container/c2f67416-7200-4dcc-9868-f320431aae20/versions/2/"
            },
            "container.manifest": {
                "count": 10,
                "href": "/pulp/api/v3/content/container/manifests/?repository_version_removed=/pulp/api/v3/repositories/container/container/c2f67416-7200-4dcc-9868-f320431aae20/versions/2/"
            },
            "container.tag": {
                "count": 1,
                "href": "/pulp/api/v3/content/container/tags/?repository_version_removed=/pulp/api/v3/repositories/container/container/c2f67416-7200-4dcc-9868-f320431aae20/versions/2/"
            }
        }
    },
    "number": 2
}
```

## Copy Tags

Tags in one repository can be copied to another repository using the tag
copy endpoint.

When no names are specified, all tags are recursively copied. If names are
specified, only the matching tags are recursively copied.

If tag names being copied already exist in the destination repository,
the conflicting tags are removed from the destination repository and the
new tags are added. This action is not recursive, no manifests or blobs
are removed.

Again we start with a new destination repository.

```bash
pulp container repository create --name second2
```

With copy (contrasted to recursive add) we do not need to retrieve the
href of the tag. Rather, we can specify the tag by source repository and
name.

```bash
pulp container repository copy-tag --name second2 --tag manifest_a --source test
```

New Repository Version:

```
{
    "pulp_created": "2019-09-10T13:42:12.572859Z",
    "pulp_href": "/pulp/api/v3/repositories/container/container/2b1c6d76-c369-4f31-8eb8-9d5d92bb2346/versions/1/",
    "base_version": null,
    "content_summary": {
        "added": {
            "container.blob": {
                "count": 20,
                "href": "/pulp/api/v3/content/container/blobs/?repository_version_added=/pulp/api/v3/repositories/container/container/2b1c6d76-c369-4f31-8eb8-9d5d92bb2346/versions/1/"
            },
            "container.manifest": {
                "count": 10,
                "href": "/pulp/api/v3/content/container/manifests/?repository_version_added=/pulp/api/v3/repositories/container/container/2b1c6d76-c369-4f31-8eb8-9d5d92bb2346/versions/1/"
            },
            "container.tag": {
                "count": 1,
                "href": "/pulp/api/v3/content/container/tags/?repository_version_added=/pulp/api/v3/repositories/container/container/2b1c6d76-c369-4f31-8eb8-9d5d92bb2346/versions/1/"
            }
        },
        "present": {
            "container.blob": {
                "count": 20,
                "href": "/pulp/api/v3/content/container/blobs/?repository_version=/pulp/api/v3/repositories/container/container/2b1c6d76-c369-4f31-8eb8-9d5d92bb2346/versions/1/"
            },
            "container.manifest": {
                "count": 10,
                "href": "/pulp/api/v3/content/container/manifests/?repository_version=/pulp/api/v3/repositories/container/container/2b1c6d76-c369-4f31-8eb8-9d5d92bb2346/versions/1/"
            },
            "container.tag": {
                "count": 1,
                "href": "/pulp/api/v3/content/container/tags/?repository_version=/pulp/api/v3/repositories/container/container/2b1c6d76-c369-4f31-8eb8-9d5d92bb2346/versions/1/"
            }
        },
        "removed": {}
    },
    "number": 1
}
```

## Copy Manifests

Manifests in one repository can be copied to another repository using
the manifest copy endpoint.

If digests are specified, only the manifests (and their recursively
related content) will be added.

If media types are specified, only manifests matching that media type
(and their recursively related content) will be added. This allows users
to copy only manifest lists, for example.

```bash
echo "Create a task to copy all manifests from source to destination repo."
TASK_HREF=$(http POST $BASE_ADDR$SECOND_REPO_HREF'copy_manifests/' \
  source_repository=$REPO_HREF \
  | jq -r '.task')
```

New Repository Version:

```
{
    "pulp_created": "2019-09-20T13:53:04.907351Z",
    "pulp_href": "/pulp/api/v3/repositories/container/container/70450dfb-ae46-4061-84e3-97eb71cf9414/versions/2/",
    "base_version": null,
    "content_summary": {
        "added": {
            "container.blob": {
                "count": 31,
                "href": "/pulp/api/v3/content/container/blobs/?repository_version_added=/pulp/api/v3/repositories/container/container/70450dfb-ae46-4061-84e3-97eb71cf9414/versions/2/"
            },
            "container.manifest": {
                "count": 21,
                "href": "/pulp/api/v3/content/container/manifests/?repository_version_added=/pulp/api/v3/repositories/container/container/70450dfb-ae46-4061-84e3-97eb71cf9414/versions/2/"
            }
        },
        "present": {
            "container.blob": {
                "count": 31,
                "href": "/pulp/api/v3/content/container/blobs/?repository_version=/pulp/api/v3/repositories/container/container/70450dfb-ae46-4061-84e3-97eb71cf9414/versions/2/"
            },
            "container.manifest": {
                "count": 21,
                "href": "/pulp/api/v3/content/container/manifests/?repository_version=/pulp/api/v3/repositories/container/container/70450dfb-ae46-4061-84e3-97eb71cf9414/versions/2/"
            }
        },
        "removed": {}
    },
    "number": 2
}
```

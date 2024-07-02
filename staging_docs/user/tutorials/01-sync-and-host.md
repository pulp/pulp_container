# Mirror and Host Images

Users can populate their repositories with content from an external source like Docker Hub by syncing
their repository. This enables them to maintain the content in a cosistent state without depending
on external sources.

## Create a Repository

Start by creating a new repository named "foo".

```bash
pulp container repository create --name foo
```

## Create a Remote

Creating a remote object informs Pulp about an external content source. In this case, we will be
using Docker Hub, but `pulp-container` remotes can be anything that implements the registry API,
including `quay`, `google container registry`, or even another instance of Pulp.

!!! note

    Container plugin supports both Docker and OCI media types.

```bash
pulp container remote create --name foo --url "https://registry-1.docker.io" --upstream-name=pulp/test-fixture-1
```

!!! note

    Use the fields `include/exclude_tags` when a specific set of tags is needed to be mirrored
    instead of the whole repository. Note that it is also possible to filter a bunch of tags that
    matches defined criteria by leveraging wildcards.


Some registries contain signed images. Such registries provide signatures in different ways.
If a registry provides signatures via a dedicated SigStore, a URL to it should be specified in
the `sigstore` field when creating a Remote.

!!! note

    Some registries provide docker API extensions for `atomic container signature` type only, or
    have `cosign` type signatures that are stored as a separate OCI image in a registry.
    Pulp will automatically sync signatures provided via the docker API extension or cosign
    signatures stored as an OCI image.


## Sync Content

Use the remote object to kick off a synchronize task by specifying the repository to
sync with. You are telling pulp to fetch content from the remote and add to the repository.

```bash
pulp container repository sync --name foo --remote foo
```

!!! note

    In the above example, the payload contains the field `mirror=False`. This means that the
    sync will be run in the additive mode only. Set `mirror` to `True` and Pulp will pull
    in new content and remove content which was also removed from upstream.
    The same logic will be applied when `include/exclude_tags` are specified together with
    the `mirror` command, but only on the subset of tags.


!!! note

    It is not posible to push content to a repository that has been used to mirror content.

Every time you change a repository, a new repository version is created. To retrieve a list of repository
versions, use the following command:

```bash
http $BASE_URL/pulp/api/v3/repositories/container/<uuid>/versions/
```

Repository Version GET Response (when complete):

```json
{
    "pulp_created": "2019-09-05T14:29:45.563089Z",
    "pulp_href": "/pulp/api/v3/repositories/container/container/ffcf03266-f0e4-4497-8434-0fe9d94c8053/versions/1/",
    "base_version": null,
    "content_summary": {
        "added": {
            "container.blob": {
                "count": 31,
                "href": "/pulp/api/v3/content/container/blobs/?repository_version_added=/pulp/api/v3/repositories/container/container/fcf03266-f0e4-4497-8434-0fe9d94c8053/versions/1/"
            },
            "container.manifest": {
                "count": 21,
                "href": "/pulp/api/v3/content/container/manifests/?repository_version_added=/pulp/api/v3/repositories/container/container/fcf03266-f0e4-4497-8434-0fe9d94c8053/versions/1/"
            },
            "container.tag": {
                "count": 8,
                "href": "/pulp/api/v3/content/container/tags/?repository_version_added=/pulp/api/v3/repositories/container/container/fcf03266-f0e4-4497-8434-0fe9d94c8053/versions/1/"
            }
        },
        "present": {
            "container.blob": {
                "count": 31,
                "href": "/pulp/api/v3/content/container/blobs/?repository_version=/pulp/api/v3/repositories/container/container/fcf03266-f0e4-4497-8434-0fe9d94c8053/versions/1/"
            },
            "container.manifest": {
                "count": 21,
                "href": "/pulp/api/v3/content/container/manifests/?repository_version=/pulp/api/v3/repositories/container/container/fcf03266-f0e4-4497-8434-0fe9d94c8053/versions/1/"
            },
            "container.tag": {
                "count": 8,
                "href": "/pulp/api/v3/content/container/tags/?repository_version=/pulp/api/v3/repositories/container/container/fcf03266-f0e4-4497-8434-0fe9d94c8053/versions/1/"
            }
        },
        "removed": {}
    },
    "number": 1
}
```

!!! note

    To set up a regular sync task, use one of the external tools that deal with periodic background jobs.
    Learn more about scheduling tasks [here](https://docs.pulpproject.org/pulpcore/workflows/scheduling-tasks.html).

## Host and Consume a Repository

This section assumes that you have a repository with content in it. Follow the previous sections to
do so.

### Create a Distribution

Container Distributions can be used to serve the Container registry API
containing the content in a repository's latest version or a specified
repository version.

```
pulp container distribution create --name foo --base-path foo --repository foo
```

### Pull and Run an Image

Once a distribution is configured to host a repository with Container
images in it, that content can be consumed by container clients.

!!! note

    An administrator is expected to configure the environment in advance to enable users to consume
    content with authorized access. Otherwise, the registry will not be able to serve the requested
    content flawlessly. In Pulp, the token authentication is enabled by default and does not come
    pre-configured out of the box.


#### Podman

```
podman pull localhost:24817/foo
```

If SSL has not been setup for your Pulp, configure podman to work with the insecure registry.
Edit the file `/etc/containers/registries.conf.` and add:

```
[registries.insecure]
registries = ['localhost:24817']
```

More info:
<https://www.projectatomic.io/blog/2018/05/podman-tls/>

#### Docker

If SSL has not been setup for your Pulp, configure docker to work with the insecure registry:

Edit the file `/etc/docker/daemon.json` and add:

```
{
    "insecure-registries" : ["localhost:24817"]
}
```

More info:
<https://docs.docker.com/registry/insecure/#deploy-a-plain-http-registry>

=== "Script"

    ```bash
    sudo docker login -u admin -p password localhost:24817
    sudo docker run localhost:24817/foo
    ```

=== "Output"

    ```
    Unable to find image 'localhost:24817/test:latest' locally
    Trying to pull repository localhost:24817/test ...
    sha256:451ce787d12369c5df2a32c85e5a03d52cbcef6eb3586dd03075f3034f10adcd: Pulling from localhost:24817/test
    1b930d010525: Pull complete
    Digest: sha256:451ce787d12369c5df2a32c85e5a03d52cbcef6eb3586dd03075f3034f10adcd
    Status: Downloaded newer image for localhost:24817/test:latest

    Hello from Docker!
    This message shows that your installation appears to be working correctly.

    To generate this message, Docker took the following steps:
     1. The Docker client contacted the Docker daemon.
     2. The Docker daemon pulled the "hello-world" image from the Docker Hub.
        (amd64)
     3. The Docker daemon created a new container from that image which runs the
        executable that produces the output you are currently reading.
     4. The Docker daemon streamed that output to the Docker client, which sent it
        to your terminal.

    To try something more ambitious, you can run an Ubuntu container with:
     $ docker run -it ubuntu bash

    Share images, automate workflows, and more with a free Docker ID:
     https://hub.docker.com/

    For more examples and ideas, visit:
     https://docs.docker.com/get-started/
    ```

!!! note

    When using a container client that cannot handle requested manifests in the new format
    (schema 2), the manifests will **not** be rewritten into the old format (schema 1) and Pulp will
    raise a 404 (HTTPNOTFOUND) error.

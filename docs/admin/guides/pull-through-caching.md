# Configure Pull-Through Caching

!!! warning

    This feature is provided as a tech preview and could change in backwards incompatible
    ways in the future.

The Pull-Through Caching feature offers an alternative way to host content by leveraging a **remote
registry** as the source of truth. This eliminates the need for in-advance repository
synchronization because Pulp acts as a **caching proxy** and stores images, after they have been
pulled by an end client, in a local repository.

## Configuring the caching:

```
# initialize a pull-through remote (the concept of upstream-name is not applicable here)
REMOTE_HREF=$(http ${BASE_ADDR}/pulp/api/v3/remotes/container/pull-through/ name=docker-cache url=https://registry-1.docker.io | jq -r ".pulp_href")

# create a pull-through distribution linked to the initialized remote
http ${BASE_ADDR}/pulp/api/v3/distributions/container/pull-through/ remote=${REMOTE_HREF} name=docker-cache base_path=docker-cache
```

Pulling content:

```
podman pull localhost:24817/docker-cache/library/busybox
```

In the example above, the image "busybox" is pulled from *DockerHub* through the "docker-cache"
distribution, acting as a transparent caching layer.

By incorporating the Pull-Through Caching feature into standard workflows, users **do not need** to
pre-configure a new repository and sync it to facilitate the retrieval of the actual content. This
speeds up the whole process of shipping containers from its early management stages to distribution.
Similarly to on-demand syncing, the feature also **reduces external network dependencies**, and
ensures a more reliable container deployment system in production environments.

!!! note

    During the pull-through operation, Pulp creates a local repository that maintains a single
    version for pulled images. For instance, when pulling an image like "debian:10," a local
    repository named "debian" with the tag "10" is created. Subsequent pulls, such as "debian:11,"
    generate a new repository version that incorporates both the "10" and "11" tags, automatically
    removing the previous version. Repositories and their content remain manageable through standard
    Pulp API endpoints. The repositories are read-only and public by default.


!!! info

    Removing a pull-through remote associated to a distribution may result in errors when attempting
    to retrieve content not yet cached in Pulp.


### Filtering the repositories

It is possible to use the includes/excludes fields to set a list of upstream repositories that Pulp
will be able to pull from.

```
# define a pull-through remote with the includes/excludes fields
REMOTE_HREF=$(http ${BASE_ADDR}/pulp/api/v3/remotes/container/pull-through/ name=docker-cache url=https://registry-1.docker.io includes=["*pulp*"] excludes=["*molecule_debian*"] | jq -r ".pulp_href")

# create a pull-through distribution linked to the initialized remote
http ${BASE_ADDR}/pulp/api/v3/distributions/container/pull-through/ remote=${REMOTE_HREF} name=docker-cache base_path=docker-cache
```

Pulling allowed content:

```
podman pull localhost:24817/docker-cache/pulp/test-fixture-1:manifest_a
```

Pulling from a repository that includes *molecule_debian* in its name will fail because it is filtered by the *excludes* definition:
```
podman pull localhost:24817/docker-cache/pulp/molecule_debian11
Error response from daemon: repository localhost:24817/docker-cache/pulp/molecule_debian11 not found: name unknown: Repository not found.
```

Since only repositories with *pulp* in their names are included (`includes=["*pulp*"]`), the following image pull will also fail:

```
podman pull localhost:24817/docker-cache/library/hello-world
Error response from daemon: repository localhost:24817/docker-cache/library/hello-world not found: name unknown: Repository not found.
```

# Role-based Access Control

Role-based access control (RBAC) **restricts** access to entities based on a user's role within an
organization. A role consists of one or more permissions. Users having a proper set of roles can
view, modify, or delete resources hosted on different endpoints.

By default, container repositories' content is accessible via `podman` or `docker` pull
commands, unless the opposite is *explicitly* specified. A private repository can be created via the
REST API for container distributions. An existing distribution can be updated with the parameter
`private=True`.

!!! note

    Users logged in as administrators (superusers) always bypass any authorization checks.

## Roles

Role based access control (RBAC) is configured using access policies for the following endpoints:

- `pulp_container/namespaces`
- `distributions/container/container`
- `repositories/container/container-push`
- `remotes/container/container`
- `repositories/container/container`
- `repositories/container/container-push/versions`
- `repositories/container/container/versions`
- `content/container/blobs`
- `content/container/manifests`
- `content/container/tags`

### Default Roles

For each endpoint, a different set of roles is defined. The roles can be assigned at the model
or object level for every user or group. In the following sections, the *Creator*, *Owner*,
*Consumer*, and *Collaborator* roles are introduced. The *Consumer* and *Collaborator* roles are
defined only for namespaces and distributions (i.e., container repositories served by the Pulp Registry).

#### Creator Role

The *Creator* role contains the `add` permission for objects present on a particular endpoint.
For the distributions endpoint, only users with the `container.add_containerdistribution`
permission can create objects:

```bash
pulp role show --name "container.containerdistribution_creator"
```

```
{
  "pulp_href": "/pulp/api/v3/roles/1a8555c8-3bfc-4688-81e3-5bf6fa38b9d7/",
  "pulp_created": "2022-05-26T12:02:28.872667Z",
  "name": "container.containerdistribution_creator",
  "description": null,
  "permissions": [
    "container.add_containerdistribution"
  ],
  "locked": true
}
```

To perform operations on an endpoint (aka ViewSet actions), a user may need to have additional
permissions. One of the following *conditions* need to be satisfied to create a new distribution:

```bash
pulp access-policy show --viewset-name "distributions/container/container" | jq -r '.statements[] | select(.action[] | contains("create"))'
```

```
{
  "action": [
    "create"
  ],
  "effect": "allow",
  "condition": "has_namespace_model_perms",
  "principal": "authenticated"
}
{
  "action": [
    "create"
  ],
  "effect": "allow",
  "condition": "has_namespace_perms:container.add_containerdistribution",
  "principal": "authenticated"
}
{
  "action": [
    "create"
  ],
  "effect": "allow",
  "condition": "namespace_is_username",
  "principal": "authenticated"
}
```

!!! note

    A user with the *Creator* role for namespaces does not need to have any additional roles to
    create distributions within the given namespaces. Similarly, the user is allowed to create
    distributions within the owning username namespace (e.g., user `alice` can create container
    repositories like `alice/repo1`).


#### Owner Role

The *Owner* role contains all of the permissions available for the associated ViewSet apart from
the `add` permission. For the ViewSet hosting namespaces, the set of permissions reads:

```bash
pulp role show --name "container.containernamespace_owner"
```

```
{
  "pulp_href": "/pulp/api/v3/roles/1f5519f5-5b2d-47cc-b081-2f38f256740e/",
  "pulp_created": "2022-05-26T12:02:28.999330Z",
  "name": "container.containernamespace_owner",
  "description": null,
  "permissions": [
    "container.delete_containernamespace",
    "container.manage_roles_containernamespace",
    "container.namespace_add_containerdistribution",
    "container.namespace_change_containerdistribution",
    "container.namespace_change_containerpushrepository",
    "container.namespace_delete_containerdistribution",
    "container.namespace_modify_content_containerpushrepository",
    "container.namespace_pull_containerdistribution",
    "container.namespace_push_containerdistribution",
    "container.namespace_view_containerdistribution",
    "container.namespace_view_containerpushrepository",
    "container.view_containernamespace"
  ],
  "locked": true
}
```

Besides the permissions for *Read*, *Update*, and *Delete* actions, the *Owner* role has the
`mange_roles` permission that allows the user to call the ViewSet's `add_role` and
`remove_role` endpoints for easy management of roles around that ViewSet's object.

The *Owner* role for namespaces contains permissions for any additional action that can be performed
on the related endpoints. The endpoints serving content for container clients permit access to
container distributions/repositories based on the presence of `pull_containerdistribution` and
`push_containerdistributuion` permissions.

!!! note

    Repositories of the push type created with container clients (e.g., by running `podman push`)
    are considered public and anyone can `pull` the images from them.


#### Consumer Role

The *Consumer* role contains only the `view` and `pull` permissions. Below, a list of associated
permissions for distributions is showcased:

```bash
pulp role show --name "container.containerdistribution_consumer"
```

```
{
  "pulp_href": "/pulp/api/v3/roles/7b97928a-5d33-454f-982e-41cfe102b273/",
  "pulp_created": "2022-05-26T12:02:28.945828Z",
  "name": "container.containerdistribution_consumer",
  "description": null,
  "permissions": [
    "container.pull_containerdistribution",
    "container.view_containerdistribution"
  ],
  "locked": true
}
```

Having the `view` and `pull` permissions allows a user to see and pull content from the Pulp
Registry. Assigning this role only at the object level allows administrators and owners to select
what the user can see.

```bash
pulp container distribution create --name "foo" --base-path "bar"
pulp user create --username "consumer"
pulp container distribution role add --name "foo" --user "consumer" --role "container.containerdistribution_consumer"
pulp user role-assignment list --username "consumer"
```

```
[
  {
    "pulp_href": "/pulp/api/v3/users/44/roles/6e58251d-7656-4c0d-9630-ea51ed7c29b5/",
    "pulp_created": "2022-05-27T15:27:00.623004Z",
    "role": "container.containerdistribution_consumer",
    "content_object": "/pulp/api/v3/distributions/container/container/5b8ec13c-d578-4b3a-9b99-80986e5e00b6/"
  }
]
```

Also, it is possible to assign the role in the following manner:

```bash
PULP_HREF=$(pulp container distribution show --name "foo" | jq -r ".pulp_href")
pulp user role-assignment add --object ${PULP_HREF} --username "consumer" --role "container.containerdistribution_consumer"
```

#### Collaborator Role

The *Collaborator* role represents a set of permissions that a co-worker working within a same user-space
should have. In addition to the *Consumer* role, users with the *Collaborator* role are allowed
to add (push) and modify content. The following set of permissions is evaluated for the *Collaborator*
role for distributions:

```bash
pulp role show --name "container.containerdistribution_collaborator"
```

```
{
  "pulp_href": "/pulp/api/v3/roles/933e0376-8945-489a-93a6-cafb6753f4bb/",
  "pulp_created": "2022-05-26T12:02:28.924330Z",
  "name": "container.containerdistribution_collaborator",
  "description": null,
  "permissions": [
    "container.pull_containerdistribution",
    "container.push_containerdistribution",
    "container.view_containerdistribution"
  ],
  "locked": true
}
```

```bash
pulp role show --name "container.containernamespace_collaborator"
```

```
{
  "pulp_href": "/pulp/api/v3/roles/1466e614-73a7-4a58-ab36-ced0ab1a1809/",
  "pulp_created": "2022-05-26T12:02:29.058226Z",
  "name": "container.containernamespace_collaborator",
  "description": null,
  "permissions": [
    "container.namespace_add_containerdistribution",
    "container.namespace_change_containerdistribution",
    "container.namespace_change_containerpushrepository",
    "container.namespace_delete_containerdistribution",
    "container.namespace_modify_content_containerpushrepository",
    "container.namespace_pull_containerdistribution",
    "container.namespace_push_containerdistribution",
    "container.namespace_view_containerdistribution",
    "container.namespace_view_containerpushrepository",
    "container.view_containernamespace"
  ],
  "locked": true
}
```

## Permissions

A role is defined by one or more permissions. In this section, details of permissions used within
the container plugin are discussed.

!!! warning

    The concept of managing granular permissions is obsolete. As of release 2.11.0, the plugin uses
    `roles` instead of separate permission classes. To migrate the customized permission
    classes to roles, follow the instructions shown at `migrating-perms-to-roles`.


### Namespaces

Pulp Container namespaces allow users to reuse repository names under different context. The
namespace can represent an organization, a team, or any other kind of logical grouping of container
repositories. Namespaces provide a naming convention for container repositories. Repositories in
the `foo` namespace are named `foo/something` and `foo/something-else`.

The default access policy for `pulp_container/namespaces` requires a user to have the
`container.add_containernamespace` permission to create a new namespace. Alternatively a user is
allowed to create a namespace that matches his username if it did not exist before. The new
namespace can be created by pushing an image using `podman` or `docker` client. This same
permissions allow the user of Pulp's API to create a new namespace.

The creation of a new namespace creates three user groups that can access the namespace:
Owners, Collaborators, and Consumers. The user that creates the namespace is automatically added to
the Owners group.

#### Namespace Owners

The group name is `container.namespace.owners.<namespace name>`. This group has the following
object permissions for the namespace:

```
"container.view_containernamespace"
"container.delete_containernamespace"
"container.namespace_add_containerdistribution",
"container.namespace_delete_containerdistribution
"container.namespace_view_containerdistribution"
"container.namespace_pull_containerdistribution"
"container.namespace_push_containerdistribution"
"container.namespace_change_containerdistribution"
"container.namespace_view_containerpushrepository"
"container.namespace_modify_content_containerpushrepository"
"container.namespace_modify_content_containerrepository"
```

The users in the owners group have the permissions to add/remove users from all three groups
associated with the namespace. They also have the ability to create, update, and delete
repositories in the namespace.

In addition to being able to use the `podman` or `docker` client to manage repositories, owners
can use Pulp's API to add and remove tags in the repositories for the namespace.

#### Namespace Collaborators

The group name is `container.namespace.collaborators.<namespace name>`. This group has the
following object permissions for the namespace:

```
"container.view_containernamespace"
"container.namespace_add_containerdistribution"
"container.namespace_delete_containerdistribution"
"container.namespace_view_containerdistribution"
"container.namespace_pull_containerdistribution"
"container.namespace_push_containerdistribution"
"container.namespace_change_containerdistribution"
"container.namespace_view_containerpushrepository"
"container.namespace_modify_content_containerpushrepository"
"container.namespace_modify_content_containerrepository"
```

Users in the Collaborator group can do everything that the owners can, with the exception of
deleting the namespace.

#### Namespace Consumers

The group name is `container.namespace.consumers.<namespace name>`. This group has the following
object permissions for the namespace:

```
"container.view_containernamespace"
"container.namespace_view_containerdistribution"
"container.namespace_pull_containerdistribution"
"container.namespace_view_containerpushrepository"
```

Users in the Consumers group can `pull` from any of the repositories in the namespace. Users
should only need to be added to this group if private repositories are being used. If the
repository is public, then anyone can `pull` from the repository.

### Distributions

Distributions are Pulp resources that represent URLs where repositories can be consumed.
Permissions for accessing specific container repositories are described in terms of permissions
to access Container Distributions. Each time a new repository is pushed using `podman` or `docker`,
a Container Distribution is created. There is also a Container Push Repository created. Both of
these resources can be accessed using Pulp's API.

The creation of a new distribution creates three user groups that can access the distribution:
Owners, Collaborators, and Consumers. The user that creates the distribution is automatically added to
the Owners group.

#### Distribution Owners

The group name is `container.distribution.owners.<distribution uuid>`. This group has the following
object permissions for the Distribution:

```
"container.view_containerdistribution"
"container.pull_containerdistribution"
"container.push_containerdistribution"
"container.delete_containerdistribution"
"container.change_containerdistribution"
```

The Owners group also has the following permissions for the Container Push Repository associated
with the Distribution:

```
"container.view_containerpushrepository"
"container.modify_content_containerpushrepository"
```

The owners of a Container Distribution have the ability to update and delete the repository
associated with the Distribution. They can also add/remove users from the groups associated with
the distribution.

#### Distribution Collaborators

The group name is `container.distribution.collaborators.<distribution uuid>`. This group has the
following object permissions for the Distribution:

```
"container.view_containerdistribution"
"container.pull_containerdistribution"
"container.push_containerdistribution"
```

The Collaborators group also has the following permissions for the Container Push Repository associated
with the Distribution:

```
"container.view_containerpushrepository"
"container.modify_content_containerpushrepository"
```

Users in the Collaborator group can do everything that the owners can, with the exception for deleting
the Distribution.

#### Distribution Consumers

The group name is `container.distribution.consumers.<distribution uuid>`. This group has the following
object permissions for the distribution:

```
"container.view_containerdistribution"
"container.pull_containerdistribution"
```

The Consumers group also has the following permissions for the Container Push Repository associated
with the Distribution:

```
"container.view_containerpushrepository"
```

Users in the Consumers group can the `pull` the repository. Users should only need to be added to
this group if the Distribution has been configured with `private=True`. If the Distribution is
public, then anyone can `pull` from the repository associated with the Distribution.


#### Pull-through Distribution Owners

This role allows users to manage and pull content from the pull-through cache distribution.

```
"container.view_containerpullthroughdistribution"
"container.delete_containerpullthroughdistribution"
"container.change_containerpullthroughdistribution"
"container.manage_roles_containerpullthroughdistribution"
"container.pull_new_containerdistribution"
```

#### Pull-through Distribution Collaborators

Users who have this role assigned can preview and pull new content from the main pull-through cache
distribution.

```
"container.view_containerpullthroughdistribution"
"container.pull_new_containerdistribution"
```

#### Pull-through Distribution Consumers

Similarly to the collaborator role, the following set of permissions is set for the consumer role:

```
"container.view_containerpullthroughdistribution"
"container.pull_new_containerdistribution"
```

It is recommended to assign at least one role with these permissions to allow users to pull new
content from a remote repository:
```
"container.namespace_modify_content_containerrepository" (e.g., namespace collaborator)
"container.namespace_add_containerdistribution" (e.g., namespace collaborator)
"container.pull_new_containerdistribution" (e.g., pull-through cache consumer)
```

Users without the permissions can still pull already cached content from Pulp. This behaviour is
further restricted by flagging a distribution as `private=True`.

### Private Repositories

Users wishing to `pull` from a Container Distribution with `private=True`
will require the following object level permission on the Distribution:

```
"container.pull_containerdistribution"
```

Users that wish to be able to access the distribution with Pulp's API need the following object level
permission on the Distribution:

```
"container.view_containerdistribution"
```

Users that wish to be able to access the repository associated with the distribution with Pulp's
API need the following object level permission on the Container Push Repository:

```
"container.view_containerpushrepository"
```

# Role-based Access Control

Role-based access control (RBAC) **restricts** access to entities based on a user's role within an
organization. A role consists of one or more permissions. Users having a proper set of roles can
view, modify, or delete resources hosted on different endpoints.

By default, the content in container repositories that have been distributed is public and accessible with `podman` or `docker pull`. Unless the container distribution is marked `private=True`, anyone can view and download the images available in these repositories. Push and delete permission is restricted to those with the *Owner* or *Collaborator* roles on the image's namespace or distribution.

!!! note
    Users logged in as administrators (superusers) always bypass any authorization checks.

## Namespaces

Permissions in `pulp-container` start with Namespaces, a grouping primative used to tie docker repositories together under a shared organization or team. In `pulp-container` the namespace is always the first part of an image's name, e.g. image `foo/hello` is under the namespace `foo` and image `bar` is under the namespace `bar`. Each container distribution links to a namespace with the same name as the first part of the distribution's `base_path` (since `base_path` is what determines the image's name).

The default access policy for `pulp_container/namespaces` requires a user to have the `container.containernamespace_creator` role to create a new namespace. If the user has permission, then namespaces are automatically created and linked when a new distribution is created, either through the Pulp API or through a `docker push`. Namespaces can be created manually through the Pulp API before any image pushes. Also, a user is allowed to create a namespace that matches their username if it did not exist before, which they will become the owner of upon creation.

Push and pull (for private repositories) permissions are first checked through the user's namespace permissions. There are three main roles, `container.containernamespace_owner`, `container.containernamespace_collaborator` and `container.containernamespace_consumer`, each with a different set of permissions for common usecases. Each role can be assigned at the model (global), domain, or object level. Roles assigned at the model level grant that role's permissions across *all* namespaces in Pulp, domain level across all namespaces in that domain, and object level with only permissions for just that one namespace. 

### Owner Role

The *Owner* role contains all of the permissions available for the namespace except the `add` permission.

=== "Show Owner Role"

    ```bash
    pulp role show --name "container.containernamespace_owner"
    ```

=== "Output"

    ```json
    {
      "pulp_href": "/pulp/api/v3/roles/019e8eea-9bd5-7a59-9ac5-aeed87729931/",
      "prn": "prn:core.role:019e8eea-9bd5-7a59-9ac5-aeed87729931",
      "pulp_created": "2026-06-03T19:16:40.534341Z",
      "pulp_last_updated": "2026-06-03T19:25:27.207036Z",
      "name": "container.containernamespace_owner",
      "description": null,
      "permissions": [
        "container.delete_containernamespace",
        "container.manage_roles_containernamespace",
        "container.namespace_add_containerdistribution",
        "container.namespace_change_containerdistribution",
        "container.namespace_change_containerpushrepository",
        "container.namespace_change_containerrepository",
        "container.namespace_delete_containerdistribution",
        "container.namespace_modify_content_containerpushrepository",
        "container.namespace_modify_content_containerrepository",
        "container.namespace_pull_containerdistribution",
        "container.namespace_push_containerdistribution",
        "container.namespace_view_containerdistribution",
        "container.namespace_view_containerpushrepository",
        "container.namespace_view_containerrepository",
        "container.view_containernamespace"
      ],
      "locked": true
    }
    ```

User's with the owner role can manage everything about the namespace, perform any action on images within the namespace, and manage the roles of other users for this namespace. The owner role is the strongest role (outside of being an admin) and is automatically assigned to the user who created the namespace.

!!! note
    Creating the namespace requires the `container.containernamespace_creator` role or to have the same username as the name of the namespace to be created.

### Consumer Role

The *Consumer* role contains only the `view` and `pull` permissions.

=== "Show Consumer Role"

    ```bash
    pulp role show --name "container.containernamespace_consumer"
    ```

=== "Output"

    ```json
    {
      "pulp_href": "/pulp/api/v3/roles/019e8eea-9bf1-7952-a621-d9495b479a31/",
      "prn": "prn:core.role:019e8eea-9bf1-7952-a621-d9495b479a31",
      "pulp_created": "2026-06-03T19:16:40.562222Z",
      "pulp_last_updated": "2026-06-03T19:25:27.230164Z",
      "name": "container.containernamespace_consumer",
      "description": null,
      "permissions": [
        "container.namespace_pull_containerdistribution",
        "container.namespace_view_containerdistribution",
        "container.namespace_view_containerpushrepository",
        "container.namespace_view_containerrepository",
        "container.view_containernamespace"
      ],
      "locked": true
    }
    ```

Having the `view` and `pull` permissions allows a user to see and pull private content from the Pulp
Registry. Assigning this role only at the object level allows administrators and owners to select
what the user can see.

=== "Assign object level role"

    ```bash
    pulp container distribution create --name "foo" --base-path "foo/hello" --private # Creates namespace 'foo'
    pulp user create --username "consumer"
    pulp container namespace role add --name "foo" --user "consumer" --role "container.containernamespace_consumer"
    pulp user role-assignment list --username "consumer"
    ```

=== "Final call output"

    ```json
    [
      {
        "pulp_href": "/pulp/api/v3/users/128/roles/019e90b4-3933-736e-8f5f-5210b6b7d894/",
        "prn": "prn:core.userrole:019e90b4-3933-736e-8f5f-5210b6b7d894",
        "pulp_created": "2026-06-04T03:36:30.772782Z",
        "pulp_last_updated": "2026-06-04T03:36:30.772805Z",
        "role": "container.containernamespace_consumer",
        "content_object": "/pulp/api/v3/pulp_container/namespaces/019e90b3-da5d-727e-a35f-478b50a4233a/",
        "content_object_prn": "prn:container.containernamespace:019e90b3-da5d-727e-a35f-478b50a4233a",
        "description": null,
        "permissions": [
          "container.namespace_pull_containerdistribution",
          "container.namespace_view_containerdistribution",
          "container.namespace_view_containerpushrepository",
          "container.namespace_view_containerrepository",
          "container.view_containernamespace"
        ],
        "domain": null
      }
    ]
    ```

Also, it is possible to assign the role in the following manner:

```bash
PULP_HREF=$(pulp container namespace show --name "foo" | jq -r ".pulp_href")
pulp user role-assignment add --object ${PULP_HREF} --username "consumer" --role "container.containernamespace_consumer"
```

### Collaborator Role

The *Collaborator* role represents a set of permissions that a co-worker working within a same user-space
should have. In addition to the *Consumer* role, users with the *Collaborator* role are allowed
to add (push) and modify content.

=== "Show Collaborator Role"

    ```bash
    pulp role show --name "container.containernamespace_collaborator"
    ```

=== "Output"

    ```json
    {
      "pulp_href": "/pulp/api/v3/roles/019e8eea-9be6-7d41-9441-a46dd5e22cde/",
      "prn": "prn:core.role:019e8eea-9be6-7d41-9441-a46dd5e22cde",
      "pulp_created": "2026-06-03T19:16:40.551289Z",
      "pulp_last_updated": "2026-06-03T19:25:27.222189Z",
      "name": "container.containernamespace_collaborator",
      "description": null,
      "permissions": [
        "container.namespace_add_containerdistribution",
        "container.namespace_change_containerdistribution",
        "container.namespace_change_containerpushrepository",
        "container.namespace_change_containerrepository",
        "container.namespace_delete_containerdistribution",
        "container.namespace_modify_content_containerpushrepository",
        "container.namespace_modify_content_containerrepository",
        "container.namespace_pull_containerdistribution",
        "container.namespace_push_containerdistribution",
        "container.namespace_view_containerdistribution",
        "container.namespace_view_containerpushrepository",
        "container.namespace_view_containerrepository",
        "container.view_containernamespace"
      ],
      "locked": true
    }
    ```

Collaborators, like Owners, have the `container.namespace_add_containerdistribution` permission allowing them to push new images to Pulp under the same namespace, auto-creating the backing container distribution and repository. Newly pushed images are public by default, allowing anyone to view and pull from them. The user will also be granted owner roles for the created distribution and repository.

## Distributions

The second level of permissions in `pulp-container` is on Distributions, with each distribution representing an individual image that can be assigned permissions on. After checking namespace permissions, Pulp will then check to see if the user has any permissions on the distribution being accessed. Like namespaces, distributions follow the *Owner*, *Collaborator* and *Consumer* role scheme with similar permissions, just scoped to distributions instead.

=== "Show Distribution Roles"

    ```bash
    pulp role list --name-startswith "container.containerdistribution"
    ```

=== "Output"

    ```json
    [
      {
        "pulp_href": "/pulp/api/v3/roles/019e8eea-9bb8-7244-8b64-77a4c0af732c/",
        "prn": "prn:core.role:019e8eea-9bb8-7244-8b64-77a4c0af732c",
        "pulp_created": "2026-06-03T19:16:40.505460Z",
        "pulp_last_updated": "2026-06-03T19:25:27.183450Z",
        "name": "container.containerdistribution_consumer",
        "description": null,
        "permissions": [
          "container.pull_containerdistribution",
          "container.view_containerdistribution"
        ],
        "locked": true
      },
      {
        "pulp_href": "/pulp/api/v3/roles/019e8eea-9bab-7411-9fc0-080b573b616f/",
        "prn": "prn:core.role:019e8eea-9bab-7411-9fc0-080b573b616f",
        "pulp_created": "2026-06-03T19:16:40.492144Z",
        "pulp_last_updated": "2026-06-03T19:25:27.177034Z",
        "name": "container.containerdistribution_collaborator",
        "description": null,
        "permissions": [
          "container.pull_containerdistribution",
          "container.push_containerdistribution",
          "container.view_containerdistribution"
        ],
        "locked": true
      },
      {
        "pulp_href": "/pulp/api/v3/roles/019e8eea-9ba0-7b15-8ff1-0bfb19a8c069/",
        "prn": "prn:core.role:019e8eea-9ba0-7b15-8ff1-0bfb19a8c069",
        "pulp_created": "2026-06-03T19:16:40.480936Z",
        "pulp_last_updated": "2026-06-03T19:25:27.169125Z",
        "name": "container.containerdistribution_owner",
        "description": null,
        "permissions": [
          "container.change_containerdistribution",
          "container.delete_containerdistribution",
          "container.manage_roles_containerdistribution",
          "container.pull_containerdistribution",
          "container.push_containerdistribution",
          "container.view_containerdistribution"
        ],
        "locked": true
      },
      {
        "pulp_href": "/pulp/api/v3/roles/019e8eea-9b94-7b12-a7ee-e0acaf594bea/",
        "prn": "prn:core.role:019e8eea-9b94-7b12-a7ee-e0acaf594bea",
        "pulp_created": "2026-06-03T19:16:40.468877Z",
        "pulp_last_updated": "2026-06-03T19:25:27.151698Z",
        "name": "container.containerdistribution_creator",
        "description": null,
        "permissions": [
          "container.add_containerdistribution"
        ],
        "locked": true
      }
    ]
    ```

!!! note
    It is recommended to assign the namespace creator role to a user instead of the distribution creator role since creating a distribution will sometimes involve creating a new namespace if it does not already exist.

## Roles and Access Policies

The default roles and policies in `pulp-container` are configured using access policies for the following `viewset_names`:

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

### Creating Custom Roles

The default roles can not be edited as they are locked, but new unlocked roles can be created and edited.

```bash
pulp role create --name "docker-read-write" \
    --permission "container.view_containernamespace" \
    --permission "container.namespace_add_containerdistribution" \
    --permission "container.namespace_view_containerdistribution" \
    --permission "container.namespace_pull_containerdistribution" \
    --permission "container.namespace_push_containerdistribution" \
    --permission "container.namespace_view_containerpushrepository" \
    --permission "container.namespace_view_containerrepository" \
    --description "Read/Write/no delete only docker api"

# Assign new role to alice
pulp container namespace add --name "foo" --username "alice" --role "docker-read-write"
```

### Editing the Access Policies

The access policies on a viewset determine who can see the objects of the viewset, what permissions are required to perform actions on those objects, and what roles are given upon object creation. The `queryset_scoping`, `statements` and `creation_hooks` of the access policy determine these behaviors respectively. Each of these attributes can be viewed and edited individually.

```bash
# View Container Namespace's Access Policy
pulp access-policy show --viewset-name "pulp_container/namespaces"

# Update Container Namespace's Creation Hooks
pulp access-policy update --href "$NAMESPACE_AP_HREF" \
    --creation-hooks '[{"function": "add_roles", "parameters": {"roles": "docker-read-write"}}]'
```

!!! note
    Access polices can be reset to their default using the reset endpoint, e.g: pulp access-policy reset --href "$AP_HREF"

### Docker API Permission Policies

The main roles and permission policies for the Docker API described before are found under the `distributions/container/container` and `pulp_container/namespace` viewsets. Specifically the Container Distribution access policy contains special action statements that are used when determining the permissions a user has to perform a Docker action.

#### `docker/podman pull`

When pulling an image Pulp will check the `pull` action on the Container Distribution access policy.

=== "Show `pull` Action Statements"

    ```bash
    pulp access-policy show --viewset-name "distributions/container/container" \
      | jq '.statements[] | select(.action[] == "pull")'
    ```

=== "Output"

    ```json
    {
      "action": [
        "pull"
      ],
      "effect": "allow",
      "principal": "*",
      "condition_expression": [
        "not is_private"
      ]
    }
    {
      "action": [
        "pull"
      ],
      "effect": "allow",
      "condition": [
        "has_namespace_or_obj_perms:container.pull_containerdistribution"
      ],
      "principal": "authenticated"
    }
    ```

There are two action statements for `pull`, only one of them needs to be true for the user to be granted permission to pull an image. The order of statements is the order the statements are checked. So first Pulp checks if the distribution is public, i.e. `not is_private`. If the distribution is private than we check if the user has permission on the namespace or distribution. See the section below describing the custom conditions available for `pulp-container`.

!!! note
    If no statement evaluates to true then the request is denied. Admins always bypass any checks.

#### `docker/podman push`

When pushing an image to Pulp there are three different scenarios a user can find themselves in which determines the permissions that are checked for during the push.

- Scenario 1: Pushing a new image and a new namespace
- Scenario 2: Pushing a new image inside an existing namespace
- Scenario 3: Pushing a new tag/manifest for an existing image

Let's start with Scenario 3 which requires the least amount of permissions and only checks the `push` action on the Container Distribution access policy.

=== "Show `push` Action Statements"

    ```bash
    pulp access-policy show --viewset-name "distributions/container/container" \
      | jq '.statements[] | select(.action[] == "push")'
    ```

=== "Output"

    ```json
    {
      "action": [
        "push"
      ],
      "effect": "allow",
      "condition": [
        "has_namespace_or_obj_perms:container.push_containerdistribution",
        "obj_exists"
      ],
      "principal": "authenticated"
    }
    {
      "action": [
        "push"
      ],
      "effect": "allow",
      "condition": [
        "has_namespace_or_obj_perms:container.add_containerdistribution",
        "has_namespace_or_obj_perms:container.push_containerdistribution"
      ],
      "principal": "authenticated"
    }
    ```

The first statement checks that the request isn't a first push, our Scenario 3. Both of the two action statements for `push` check to see if the user has the `container.push_containerdistribution` permission on the namespace or distribution. This permission can be found in both the Distribution's and Namespace's *Owner* and *Collaborator* roles.

!!! note
    Each condition inside a statement's `condition` list is AND together.

For Scenario 2 Pulp will check the `create_distribution` action on the Namespace access policy.

=== "Show `create_distribution` Action Statement"

    ```bash
    pulp access-policy show --viewset-name "pulp_container/namespaces"   | jq '.statements[] | select(.action[] == "create_distribution")'
    ```

=== "Output"

    ```json
    {
      "action": [
        "create_distribution"
      ],
      "effect": "allow",
      "condition": "has_model_or_domain_or_obj_perms:container.namespace_add_containerdistribution",
      "principal": "authenticated"
    }
    ```

In order to create a new distribution inside the existing namespace, the user needs the `container.namespace_add_containerdistribution` permission. This permission is a part of the Namespace *Owner* and *Collobarator* roles.

And for Scenario 1 Pulp checks the `create` action on the Namespace access policy.

=== "Show `create` Action Statement"

    ```bash
    pulp access-policy show --viewset-name "pulp_container/namespaces"   | jq '.statements[] | select(.action[] == "create")'
    ```

=== "Output"

    ```json
    {
      "action": [
        "create"
      ],
      "effect": "allow",
      "condition": "has_model_or_domain_perms:container.add_containernamespace",
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

If the user has permission to create the namespace, then they will be granted the Namespace Owner role for the new namespace, which in turn will grant them the permission to create the distribution for the new image.

#### `skopeo list-tags`

Pulp also supports the `v2/_catalog` endpoint for each repository allowing a user to see the available tags for that image. This checks the `catalog` action on the Container Distribution access policy.

```bash
pulp access-policy show --viewset-name "distributions/container/container" \
  | jq '.statements[] | select(.action[] == "catalog")'

{
  "action": [
    "catalog"
  ],
  "effect": "allow",
  "principal": "authenticated"
}
```

Any logged in user can list out the tags for an image.

### Custom Queryset Scoping

In `pulp-container` there are custom queryset scoping methods for the Content, Repository, and Distribution viewsets. These custom methods are used to enforce the Namespace permissions and public/private behavior of repositories, but only for the Pulp APIs, they have no effect on the Docker APIs.

```bash
pulp access-policy show --viewset-name "repositories/container/container" | jq '.queryset_scoping'

# Ensure we can see every repository that is public or we have permission on through namespaces/distributions
{
  "function": "get_container_repos_qs",
  "parameters": {
    "ns_perm": "container.view_containernamespace",
    "dist_perm": "container.view_containerdistribution",
    "repo_perm": "container.view_containerrepository"
  }
}
```

### `pulp-container`'s Custom Access Conditions

::: pulp_container.app.global_access_conditions

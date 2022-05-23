.. _roles:

Roles
=====

Role based access control (RBAC) is configured using access policies for the following endpoints:

* ``pulp_container/namespaces``
* ``distributions/container/container``
* ``repositories/container/container-push``
* ``remotes/container/container``
* ``repositories/container/container``
* ``repositories/container/container-push/versions``
* ``repositories/container/container/versions``
* ``content/container/blobs``
* ``content/container/manifests``
* ``content/container/tags``


Default Roles
-------------

For each endpoint, a different set of roles is defined. The roles can be assigned at the model
or object level for every user or group. In the following sections, the *Creator*, *Owner*,
*Consumer*, and *Collaborator* roles are introduced. The *Consumer* and *Collaborator* roles are
defined only for namespaces and distributions (i.e., container repositories served by the Pulp Registry).

Creator Role
~~~~~~~~~~~~

The *Creator* role contains the ``add`` permission for objects present on a particular endpoint.
For the distributions endpoint, only users with the ``container.add_containerdistribution``
permission can create objects:

.. code-block:: bash

    pulp role show --name "container.containerdistribution_creator"

::

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

To perform operations on an endpoint (aka ViewSet actions), a user may need to have additional
permissions. One of the following *conditions* need to be satisfied to create a new distribution:

.. code-block:: bash

    pulp access-policy show --viewset-name "distributions/container/container" | jq -r '.statements[] | select(.action[] | contains("create"))'

::

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

.. note::

    A user with the *Creator* role for namespaces does not need to have any additional roles to
    create distributions within the given namespaces. Similarly, the user is allowed to create
    distributions within the owning username namespace (e.g., user ``alice`` can create container
    repositories like ``alice/repo1``).


Owner Role
~~~~~~~~~~

The *Owner* role contains all of the permissions available for the associated ViewSet apart from
the ``add`` permission. For the ViewSet hosting namespaces, the set of permissions reads:

.. code-block:: bash

    pulp role show --name "container.containernamespace_owner"

::

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

Besides the permissions for *Read*, *Update*, and *Delete* actions, the *Owner* role has the
``mange_roles`` permission that allows the user to call the ViewSet's ``add_role`` and
``remove_role`` endpoints for easy management of roles around that ViewSet's object.

The *Owner* role for namespaces contains permissions for any additional action that can be performed
on the related endpoints. The endpoints serving content for container clients permit access to
container distributions/repositories based on the presence of ``pull_containerdistribution`` and
``push_containerdistributuion`` permissions.

.. note::

    Repositories of the push type created with container clients (e.g., by running ``podman push``)
    are considered public and anyone can ``pull`` the images from them.


Consumer Role
~~~~~~~~~~~~~

The *Consumer* role contains only the ``view`` and ``pull`` permissions. Below, a list of associated
permissions for distributions is showcased:

.. code-block:: bash

    pulp role show --name "container.containerdistribution_consumer"

::

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

Having the ``view`` and ``pull`` permissions allows a user to see and pull content from the Pulp
Registry. Assigning this role only at the object level allows administrators and owners to select
what the user can see.

.. code-block:: bash

    pulp container distribution create --name "foo" --base-path "bar"
    pulp user create --username "consumer"
    pulp container distribution role add --name "foo" --user "consumer" --role "container.containerdistribution_consumer"
    pulp user role-assignment list --username "consumer"

::

    [
      {
        "pulp_href": "/pulp/api/v3/users/44/roles/6e58251d-7656-4c0d-9630-ea51ed7c29b5/",
        "pulp_created": "2022-05-27T15:27:00.623004Z",
        "role": "container.containerdistribution_consumer",
        "content_object": "/pulp/api/v3/distributions/container/container/5b8ec13c-d578-4b3a-9b99-80986e5e00b6/"
      }
    ]

Also, it is possible to assign the role in the following manner:

.. code-block:: bash

    PULP_HREF=$(pulp container distribution show --name "foo" | jq -r ".pulp_href")
    pulp user role-assignment add --object ${PULP_HREF} --username "consumer" --role "container.containerdistribution_consumer"


Collaborator Role
~~~~~~~~~~~~~~~~~

The *Collaborator* role represents a set of permissions that a co-worker working within a same user-space
should have. In addition to the *Consumer* role, users with the *Collaborator* role are allowed
to add (push) and modify content. The following set of permissions is evaluated for the *Collaborator*
role for distributions:

.. code-block:: bash

    pulp role show --name "container.containerdistribution_collaborator"

::

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


.. code-block:: bash

    pulp role show --name "container.containernamespace_collaborator"

::

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

Customizing Roles
-----------------

In Pulp, administrators are allowed to create or update roles. To create a role with permissions
required only for syncing content, one can do the following:

.. code-block:: bash

    pulp role create --name "container.containerrepository_syncer" \
        --permission "container.view_containerrepository" \
        --permission "container.view_containerremote" \
        --permission "container.change_containerrepository" \
        --permission "container.modify_content_containerrepository" \
        --permission "container.sync_containerrepository"

    pulp user role-assignment add --username "alice" --role "container.containerrepository_syncer" object ""

Customizing Access Policies
---------------------------

The plugin is shipped with default access policies that can be modified to achieve different RBAC
behaviour. For instance, update creation hooks accordingly:

.. code-block:: bash

    pulp access-policy update --viewset-name "repositories/container/container" --creation-hooks '[{"function": "add_roles_for_object_creator", "parameters": {"roles": "container.containerrepository_syncer"}}]'

.. note::

    Access polices can be reset to their defaults using the ``pulp access-policy reset`` command.

.. note::

    Customizing the access policy will cause any future changes to the default policies, like
    statement changes and bug fixes, to be ignored unless reset to the default policy.

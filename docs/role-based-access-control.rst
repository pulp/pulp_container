Role Based Access Control
=========================

Role based access control in Pulp Container is configured using Access Policies for the following
``viewset_names``:

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

This document describes the default access policies shipped with Pulp Container. Each of the above
policies can be modified to achieve a different RBAC behavior.

Repositories that are created using ``podman push`` or ``docker push`` are considered public and anyone
can ``pull`` the images from them. See below about creating private repositories.

Namespaces
----------

Pulp Container namespaces allow users to reuse repository names under different context. The
namespace can represent an organization, a team, or any other kind of logical grouping of container
repositories. Namespaces provide a naming convention for container repositories. Repositories in
the ``foo`` namespace are named ``foo/something`` and ``foo/something-else``.

The default access policy for ``pulp_container/namespaces`` requires a user to have the
``container.add_containernamespace`` permission to create a new namespace. The new namespace can be
created by pushing an image using ``podman`` or ``docker`` client. This same permission allows the user
of Pulp's API to create a new namespace.

The creation of a new namespace creates three user groups that can access the namespace:
Owners, Collaborators, and Consumers. The user that creates the namespace is automatically added to
the Owners group.

Namespace Owners
~~~~~~~~~~~~~~~~

The group name is ``container.namespace.owners.<namespace name>``. This group has the following
object permissions for the namespace::

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

The users in the owners group have the permissions to add/remove users from all three groups
associated with the namespace. They also have the ability to create, update, and delete
repositories in the namespace.

In addition to being able to use the ``podman`` or ``docker`` client to manage repositories, owners
can use Pulp's API to add and remove tags in the repositories for the namespace.

Namespace Collaborators
~~~~~~~~~~~~~~~~~~~~~~~

The group name is ``container.namespace.collaborators.<namespace name>``. This group has the
following object permissions for the namespace::

    "container.view_containernamespace"
    "container.namespace_add_containerdistribution"
    "container.namespace_delete_containerdistribution"
    "container.namespace_view_containerdistribution"
    "container.namespace_pull_containerdistribution"
    "container.namespace_push_containerdistribution"
    "container.namespace_change_containerdistribution"
    "container.namespace_view_containerpushrepository"
    "container.namespace_modify_content_containerpushrepository"

Users in the Collaborator group can do everything that the owners can, with the exception of
deleting the namespace.

Namespace Consumers
~~~~~~~~~~~~~~~~~~~

The group name is ``container.namespace.consumers.<namespace name>``. This group has the following
object permissions for the namespace::

    "container.view_containernamespace"
    "container.namespace_view_containerdistribution"
    "container.namespace_pull_containerdistribution"
    "container.namespace_view_containerpushrepository"

Users in the Consumers group can ``pull`` from any of the repositories in the namespace. Users
should only need to be added to this group if private repositories are being used. If the
repository is public, then anyone can ``pull`` from the repository.

Distributions
-------------

Distributions are Pulp resources that represent URLs where repositories can be consumed.
Permissions for accessing specific container repositories are described in terms of permissions
to access Container Distributions. Each time a new repository is pushed using ``podman`` or ``docker``,
a Container Distribution is created. There is also a Container Push Repository created. Both of
these resources can be accessed using Pulp's API.

The creation of a new distribution creates three user groups that can access the distribution:
Owners, Collaborators, and Consumers. The user that creates the distribution is automatically added to
the Owners group.

Distribution Owners
~~~~~~~~~~~~~~~~~~~

The group name is ``container.distribution.owners.<distribution uuid>``. This group has the following
object permissions for the Distribution::

    "container.view_containerdistribution"
    "container.pull_containerdistribution"
    "container.push_containerdistribution"
    "container.delete_containerdistribution"
    "container.change_containerdistribution"

The Owners group also has the following permissions for the Container Push Repository associated
with the Distribution::

    "container.view_containerpushrepository"
    "container.modify_content_containerpushrepository"

The owners of a Container Distribution have the ability to update and delete the repository
associated with the Distribution. They can also add/remove users from the groups associated with
the distribution.

Distribution Collaborators
~~~~~~~~~~~~~~~~~~~~~~~~~~

The group name is ``container.distribution.collaborators.<distribution uuid>``. This group has the
following object permissions for the Distribution::

    "container.view_containerdistribution"
    "container.pull_containerdistribution"
    "container.push_containerdistribution"

The Collaborators group also has the following permissions for the Container Push Repository associated
with the Distribution::

    "container.view_containerpushrepository"
    "container.modify_content_containerpushrepository"

Users in the Collaborator group can do everything that the owners can, with the exception of deleting
the Distribution.

Distribution Consumers
~~~~~~~~~~~~~~~~~~~~~~

The group name is ``container.distribution.consumers.<distribution uuid>``. This group has the following
object permissions for the distribution::

    "container.view_containerdistribution"
    "container.pull_containerdistribution"

The Consumers group also has the following permissions for the Container Push Repository associated
with the Distribution::

    "container.view_containerpushrepository"

Users in the Consumers group can the ``pull`` the repository. Users should only need to be added to
this group if the Distribution has been configured with ``private=True``. If the Distribution is
public, then anyone can ``pull`` from the repository associated with the Distribution.

Private Repositories
--------------------

A private repository can be created using Pulp's API for Container Distributions. A distribution
can be created before pushing to the repository or an existing distribution can be updated with
``private=True``.

Users wishing to ``pull`` from a Container Distribution with ``private=True``
will require the following object level permission on the Distribution::

    "container.pull_containerdistribution"

Users that wish to be able to access the distribution with Pulp's API need the following object level
permission on the Distribution::

    "container.view_containerdistribution"

Users that wish to be able to access the repository associated with the distribution with Pulp's
API need the following object level permission on the Container Push Repository::

    "container.view_containerpushrepository"

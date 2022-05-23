.. _rbac-index:

Role-based Access Control
=========================

Role-based access control (RBAC) **restricts** access to entities based on a user's role within an
organization. A role consists of one or more permissions. Users having a proper set of roles can
view, modify, or delete resources hosted on different endpoints.

By default, container repositories' content is accessible via ``podman`` or ``docker`` pull
commands, unless the opposite is *explicitly* specified. A private repository can be created via the
REST API for container distributions. An existing distribution can be updated with the parameter
``private=True``.

.. note::

    Users logged in as administrators (staff) always bypass any authorization checks.

Visit the following sections to understand how the plugin implements RBAC:

.. toctree::
   :maxdepth: 2

   roles
   permissions
   migrating-perms-to-roles

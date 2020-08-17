
User Setup
==========

Ansible Installer (Recommended)
-------------------------------

We recommend that you install `pulpcore` and `pulp-container` together using the `Ansible installer
<https://github.com/pulp/pulp_installer/blob/master/README.md>`_. If you install this way, pulpcore
installation and all the following steps will be done for you.

Install ``pulpcore``
--------------------

Follow the `installation
instructions <docs.pulpproject.org/installation/instructions.html>`__
provided with pulpcore.

Install plugin
--------------

This document assumes that you have
`installed pulpcore <https://docs.pulpproject.org/installation/instructions.html>`_
into a the virtual environment ``pulpvenv``.

Users should install from **either** PyPI or source.

From PyPI
*********

.. code-block:: bash

   sudo -u pulp -i
   source ~/pulpvenv/bin/activate
   pip install pulp-container


Install ``pulp_container`` from source
**************************************

.. code-block:: bash

   sudo -u pulp -i
   source ~/pulpvenv/bin/activate
   cd pulp_container
   pip install -e .

Make and Run Migrations
-----------------------

.. code-block:: bash

   django-admin migrate container

Configure Required Settings
---------------------------

The plugin expects to have defined additional settings. These settings are required if a user wants
to use the token authentication while serving content, see :ref:`authentication`.

Run Services
------------

.. code-block:: bash

   django-admin runserver 24817
   gunicorn pulpcore.content:server --bind 'localhost:24816' --worker-class 'aiohttp.GunicornWebWorker' -w 2
   sudo systemctl restart pulpcore-resource-manager
   sudo systemctl restart pulpcore-worker@1
   sudo systemctl restart pulpcore-worker@2

Enable OCI Container Image building
-----------------------------------

Pulp container plugin can be used to build an OCI format image from a Containerfile. The plugin uses
`buildah <https://github.com/containers/buildah/>`_ to build the container image. Buildah 1.14+
must be installed on the same machine that is running pulpcore-worker processes.

The pulpcore-worker processes needs to have `/usr/bin/` in its `PATH`. The user that is running
pulpcore-worker process needs to be able to manage subordinate user ids and group ids. The range of
subordinate user ids is specified in `/etc/subuid` and the range of subordinate group ids is
specified in `/etc/subgid`. More details can be found in `buildah documentation <https://github.com
/containers/libpod/blob/master/docs/tutorials/rootless_tutorial.md#enable-user-namespaces-on-rhel7-
machines>`_.

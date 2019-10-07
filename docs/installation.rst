
User Setup
==========

Ansible Installer (Recommended)
-------------------------------

We recommend that you install `pulpcore` and `pulp-container` together using the `Ansible installer
<https://github.com/pulp/ansible-pulp/blob/master/README.md>`_. If you install this way, pulpcore
installation and all the following steps will be done for you.

Install ``pulpcore``
--------------------

Follow the `installation
instructions <docs.pulpproject.org/en/3.0/nightly/installation/instructions.html>`__
provided with pulpcore.

Install plugin
--------------

This document assumes that you have
`installed pulpcore <https://docs.pulpproject.org/en/3.0/nightly/installation/instructions.html>`_
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
   django-admin runserver 24817

Make and Run Migrations
-----------------------

.. code-block:: bash

   export DJANGO_SETTINGS_MODULE=pulpcore.app.settings
   django-admin makemigrations container
   django-admin migrate container

Run Services
------------

.. code-block:: bash

   pulp-manager runserver
   gunicorn pulpcore.content:server --bind 'localhost:24816' --worker-class 'aiohttp.GunicornWebWorker' -w 2
   sudo systemctl restart pulpcore-resource-manager
   sudo systemctl restart pulpcore-worker@1
   sudo systemctl restart pulpcore-worker@2

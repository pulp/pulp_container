
User Setup
==========

Containerized Installation
**************************

Follow the `Pulp in One Container <https://pulpproject.org/pulp-in-one-container/>`_ instructions to get started with Pulp by
leveraging OCI images. Further details are discussed in the `pulpcore documentation <https://docs.pulpproject.org/pulpcore/installation/instructions.html>`_.

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

Pulp Container Plugin
=====================

The ``pulp_container`` plugin extends `pulpcore <https://pypi.python.org/pypi/pulpcore/>`__ to support
hosting container images and container metadata, supporting ``docker pull`` and ``podman pull``.

If you are just getting started, we recommend getting to know the :doc:`basic
workflows<workflows/index>`.

Features
--------

* :ref:`Synchronize <sync-workflow>` from a Container registry that has basic or token auth
* :ref:`Create Versioned Repositories <versioned-repo-created>` so every operation is a restorable snapshot
* :ref:`Download content on-demand <create-remote>` when requested by clients to reduce disk space
* :ref:`Perform docker/podman pull <host>` from a container distribution served by Pulp
* De-duplication of all saved content
* Host content either `locally or on S3 <https://docs.pulpproject.org/en/3.0/nightly/installation/
  storage.html>`_


How to use these docs
---------------------

The documentation here should be considered **the primary documentation for managing container
related content**. All relevent workflows are covered here, with references to some pulpcore
supplemental docs. Users may also find `pulpcore's conceptual docs
<https://docs.pulpproject.org/en/3.0/nightly/concepts.html>`_ useful.

This documentation falls into two main categories:

  1. :ref:`workflows-index` show the **major features** of the contaianer plugin, with links to
     reference docs.
  2. `REST API Docs <restapi.html>`_ are automatically generated and provide more detailed
     information for each **minor feature**, including all fields and options.

Container Workflows
-------------------

.. toctree::
   :maxdepth: 1

   installation
   workflows/index
   restapi/index
   changes
   contributing


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


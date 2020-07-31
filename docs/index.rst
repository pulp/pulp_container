Pulp Container Plugin
=====================

The ``pulp_container`` plugin extends `pulpcore <https://pypi.python.org/pypi/pulpcore/>`__ to support
hosting container images and container metadata, supporting ``docker pull`` and ``podman pull``.

.. note::
   Push API is provided as a tech preview feature.

If you are just getting started, we recommend getting to know the :doc:`basic
workflows<workflows/index>`.

Features
--------

* :ref:`Synchronize <sync-workflow>` container image repositories hosted on Docker-hub, Google Container Registry,
  Quay.io, etc., in mirror or additive mode
* :ref:`Create Versioned Repositories <versioned-repo-created>` so every operation is a restorable snapshot
* :ref:`Download content on-demand <create-remote>` when requested by clients to reduce disk space
* :ref:`Perform docker/podman pull <host>` from a container distribution served by Pulp
* Curate container images by :ref:`whitelisting <create-remote>` what is mirrored from an external repository
* Curate container images by creating repository versions with :ref:`a specific set <recursive-add>` of images
* De-duplication of all saved content

Tech Preview
------------

Some additional features are being supplied as a tech preview.  There is a possibility that
backwards incompatible changes will be introduced for these particular features.  For a list of
features currently being supplied as tech previews only, see the :doc:`tech preview page
<tech-preview>`.

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
   tech-preview
   changes
   contributing


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

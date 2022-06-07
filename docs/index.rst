Pulp Container Plugin
=====================

You can use the ``pulp_container`` plugin to extend Pulp so that you can host your container registry and distribute containers in an on-premises environment.
You can synchronize from a range of Docker Registry HTTP API V2-compatible registries.
Depending on your needs, you can perform whole or partial syncs from these remote repositories, blend content from different sources, and distribute them throughout your organization using Pulp.
You can also build OCI-compatible images with Pulp Container and push them to a repository in Pulp so you can distribute private containers.

For information about why you might think about hosting your own container registry, see `5 reasons to host your container registry with Pulp <https://opensource.com/article/21/5/container-management-pulp/>`__. At the time of this article's publication, there was no native way to perform import and exports to disconnected or air-gapped environments. This has since been introduced and is available. 

If you'd like to watch a recent talk about Pulp Container and see it in action, check out `Registry Native Delivery of Software Content <https://video.fosdem.org/2021/D.infra/registrynativedeliverysoftwarecontentpulp3.mp4>`__.

If you are just getting started, we recommend getting to know the :doc:`basic
workflows<workflows/index>`.

Features
--------

* :ref:`Synchronize <sync-workflow>` container image repositories hosted on Docker-hub, Google Container Registry,
  Quay.io, etc., in mirror or additive mode
* Automatically :ref:`Creates Versioned Repositories <versioned-repo-created>` so every operation is a restorable snapshot
* :ref:`Download content on-demand <create-remote>` when requested by clients to reduce disk space
* :ref:`Perform docker/podman pull <host>` from a container distribution served by Pulp
* :ref:`Perform docker/podman push <push-workflow>` to the Pulp Registry
* Curate container images by :ref:`filtering <create-remote>` what is mirrored from an external repository
* Curate container images by creating repository versions with :ref:`a specific set <recursive-add>` of images
* :ref:`Build an OCI format image from a Containerfile <build-Containerfile-workflow>` and make it available from the Pulp Registry
* Host content either `locally or on S3 <https://docs.pulpproject.org/installation/storage.html>`_
* De-duplication of all saved content
* Support disconnected and air-gapped environments with the Pulp Import/Export facility for container repositories

Tech Preview
------------

Some additional features are being supplied as a tech preview. There is a possibility that
backwards incompatible changes will be introduced for these particular features.  For a list of
features currently being supplied as tech previews only, see the :doc:`tech preview page
<tech-preview>`.

How to use these docs
---------------------

The documentation here should be considered **the primary documentation for managing container
related content**. All relevent workflows are covered here, with references to some pulpcore
supplemental docs. Users may also find `pulpcore's conceptual docs
<https://docs.pulpproject.org/concepts.html>`_ useful.

This documentation falls into two main categories:

  1. :ref:`workflows-index` shows the **major features** of the container plugin, with links to
     reference docs.
  2. The `REST API Docs <restapi.html>`_ are automatically generated and provide more detailed
     information for each **minor feature**, including all fields and options.

Container Workflows
-------------------

.. toctree::
   :maxdepth: 1

   installation
   workflows/index
   rbac/index
   restapi/index
   authentication
   tech-preview
   changes
   contributing


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

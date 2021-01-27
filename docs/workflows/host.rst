.. _host:

Host and Consume a Container Repository 
=======================================

This section assumes that you have a repository with content in it. To do this, see the
:doc:`sync` documentation.

Create a Container Distribution to serve your Repository Version
----------------------------------------------------------------

Container Distributions can be used to serve the Container registry API
containing the content in a repository's latest version or a specified
repository version.

.. literalinclude:: ../_scripts/distribution.sh
   :language: bash

Response:

.. code::

    {
        "pulp_created": "2019-09-05T14:29:51.742086Z",
        "pulp_href": "/pulp/api/v3/distributions/container/container/1b461dac-0839-4049-aa8f-92f8e8f7f034/",
        "base_path": "test",
        "content_guard": null,
        "name": "testing-hello",
        "registry_path": "localhost:24817/test",
        "repository": "/pulp/api/v3/repositories/container/container/fcf03266-f0e4-4497-8434-0fe9d94c8053/",
        "repository_version": null
    }



Reference: `Container Distribution Usage <../restapi.html#tag/distributions>`_

Pull and run an image from Pulp
-------------------------------

Once a distribution is configured to host a repository with Container
images in it, that content can be consumed by container clients.

.. note::
    An administrator is expected to configure the environment in advance to enable users to consume
    content with authorized access. Otherwise, the registry will not be able to serve the requested
    content flawlessly. In Pulp, the token authentication is enabled by default and does not come
    pre-configured out of the box. Lean more at :ref:`authentication`.

Podman
^^^^^^

``$ podman pull localhost:24817/test:<tag_name>``

If SSL has not been setup for your Pulp, configure podman to work with the insecure registry:

Edit the file ``/etc/containers/registries.conf.`` and add::

    [registries.insecure]
    registries = ['localhost:24817']

More info:
https://www.projectatomic.io/blog/2018/05/podman-tls/

Docker
^^^^^^

If SSL has not been setup for your Pulp, configure docker to work with the insecure registry:

Edit the file ``/etc/docker/daemon.json`` and add::

    {
        "insecure-registries" : ["localhost:24817"]

    }

More info:
https://docs.docker.com/registry/insecure/#deploy-a-plain-http-registry

.. literalinclude:: ../_scripts/download_after_sync.sh
   :language: bash

Docker Output::

    Unable to find image 'localhost:24817/test:latest' locally
    Trying to pull repository localhost:24817/test ...
    sha256:451ce787d12369c5df2a32c85e5a03d52cbcef6eb3586dd03075f3034f10adcd: Pulling from localhost:24817/test
    1b930d010525: Pull complete
    Digest: sha256:451ce787d12369c5df2a32c85e5a03d52cbcef6eb3586dd03075f3034f10adcd
    Status: Downloaded newer image for localhost:24817/test:latest

    Hello from Docker!
    This message shows that your installation appears to be working correctly.

    To generate this message, Docker took the following steps:
     1. The Docker client contacted the Docker daemon.
     2. The Docker daemon pulled the "hello-world" image from the Docker Hub.
        (amd64)
     3. The Docker daemon created a new container from that image which runs the
        executable that produces the output you are currently reading.
     4. The Docker daemon streamed that output to the Docker client, which sent it
        to your terminal.

    To try something more ambitious, you can run an Ubuntu container with:
     $ docker run -it ubuntu bash

    Share images, automate workflows, and more with a free Docker ID:
     https://hub.docker.com/

    For more examples and ideas, visit:
     https://docs.docker.com/get-started/


.. note::
    When using a container client that cannot handle requested manifests in the new format
    (schema 2), the manifests are rewritten into the old format (schema 1) on-the-fly by Pulp.
    In general, the automatic conversion cannot be performed when the content is not available
    in the storage. Therefore, it may be successful only if the content was previously synced
    with the ``immediate`` policy.

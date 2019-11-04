.. _sync-workflow:

Synchronize a Repository
========================

Users can populate their repositories with content from an external source like Docker Hub by syncing
their repository.

Create a Repository
-------------------

.. literalinclude:: ../_scripts/repo.sh
   :language: bash

Repository GET Response::

   {
       "pulp_created": "2019-09-05T14:29:43.424822Z",
       "pulp_href": "/pulp/api/v3/repositories/docker/docker/fcf03266-f0e4-4497-8434-0fe9d94c8053/",
       "latest_version_href": null,
       "versions_href": "/pulp/api/v3/repositories/docker/docker/ffcf03266-f0e4-4497-8434-0fe9d94c8053/versions/",
       "description": null,
       "name": "codzo"
   }

Reference (pulpcore): `Repository API Usage
<https://docs.pulpproject.org/en/3.0/nightly/restapi.html#tag/repositories>`_

.. _create-remote:

Create a Remote
---------------

Creating a remote object informs Pulp about an external content source. In this case, we will be
using Docker Hub, but ``pulp-docker`` remotes can be anything that implements the registry API,
including `quay`, `google container registry`, or even another instance of Pulp.

.. literalinclude:: ../_scripts/remote.sh
   :language: bash

Remote GET Response::

   {
       "pulp_created": "2019-09-05T14:29:44.267406Z",
       "pulp_href": "/pulp/api/v3/remotes/docker/docker/1cc699b7-24fd-4944-bde7-86aed8ac12fa/",
       "pulp_last_updated": "2019-09-05T14:29:44.267428Z",
       "download_concurrency": 20,
       "name": "my-hello-repo",
       "policy": "immediate",
       "proxy_url": null,
       "ssl_ca_certificate": null,
       "ssl_client_certificate": null,
       "ssl_client_key": null,
       "ssl_validation": true,
       "upstream_name": "library/hello-world",
       "url": "https://registry-1.docker.io",
       "whitelist_tags": null
   }


Reference: `Docker Remote Usage <../restapi.html#tag/remotes>`_

Sync repository using a Remote
------------------------------

Use the remote object to kick off a synchronize task by specifying the repository to
sync with. You are telling pulp to fetch content from the remote and add to the repository.

.. literalinclude:: ../_scripts/sync.sh
   :language: bash

Reference: `Docker Sync Usage <../restapi.html#operation/remotes_docker_docker_sync>`_


.. _versioned-repo-created:

Repository Version GET Response (when complete):

.. code:: json

   {
       "pulp_created": "2019-09-05T14:29:45.563089Z",
       "pulp_href": "/pulp/api/v3/repositories/docker/docker/ffcf03266-f0e4-4497-8434-0fe9d94c8053/versions/1/",
       "base_version": null,
       "content_summary": {
           "added": {
               "docker.blob": {
                   "count": 31,
                   "href": "/pulp/api/v3/content/docker/blobs/?repository_version_added=/pulp/api/v3/repositories/docker/docker/ffcf03266-f0e4-4497-8434-0fe9d94c8053/versions/1/"
               },
               "docker.manifest": {
                   "count": 21,
                   "href": "/pulp/api/v3/content/docker/manifests/?repository_version_added=/pulp/api/v3/repositories/docker/docker/ffcf03266-f0e4-4497-8434-0fe9d94c8053/versions/1/"
               },
               "docker.tag": {
                   "count": 8,
                   "href": "/pulp/api/v3/content/docker/tags/?repository_version_added=/pulp/api/v3/repositories/docker/docker/ffcf03266-f0e4-4497-8434-0fe9d94c8053/versions/1/"
               }
           },
           "present": {
               "docker.blob": {
                   "count": 31,
                   "href": "/pulp/api/v3/content/docker/blobs/?repository_version=/pulp/api/v3/repositories/docker/docker/ffcf03266-f0e4-4497-8434-0fe9d94c8053/versions/1/"
               },
               "docker.manifest": {
                   "count": 21,
                   "href": "/pulp/api/v3/content/docker/manifests/?repository_version=/pulp/api/v3/repositories/docker/docker/ffcf03266-f0e4-4497-8434-0fe9d94c8053/versions/1/"
               },
               "docker.tag": {
                   "count": 8,
                   "href": "/pulp/api/v3/content/docker/tags/?repository_version=/pulp/api/v3/repositories/docker/docker/ffcf03266-f0e4-4497-8434-0fe9d94c8053/versions/1/"
               }
           },
           "removed": {}
       },
       "number": 1
   }

Reference (pulpcore): `Repository Version API Usage
<https://docs.pulpproject.org/en/3.0/nightly/restapi.html#operation/repositories_versions_read>`_

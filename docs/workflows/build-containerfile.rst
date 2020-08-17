.. _build-Containerfile-workflow:

Build an OCI image from a Containerfile
=======================================


.. warning::
    All container build APIs are tech preview in Pulp Container 1.1. Backwards compatibility when
    upgrading is not guaranteed.

    This feature may not be available in all deployments due to permission problems. `buildah`
    needs to also be installed. The user running the pulp worker process needs to be able to use
    `sudo` without a password, `though this limitation should be removed in the near future
    <https://pulp.plan.io/issues/5895>`_.

Users can add new images to a container repository by uploading a Containerfile. The syntax for
Containerfile is the same as for a Dockerfile. The same REST API endpoint also accepts a JSON
string that maps artifacts in Pulp to a filename. Any artifacts passed in are available inside the
build container at `/pulp_working_directory`.

Create a Repository
-------------------

.. literalinclude:: ../_scripts/repo.sh
   :language: bash

Repository GET Response::

   {
       "pulp_created": "2019-09-05T14:29:43.424822Z",
       "pulp_href": "/pulp/api/v3/repositories/container/container/fcf03266-f0e4-4497-8434-0fe9d94c8053/",
       "latest_version_href": null,
       "versions_href": "/pulp/api/v3/repositories/container/container/ffcf03266-f0e4-4497-8434-0fe9d94c8053/versions/",
       "description": null,
       "name": "codzo"
   }

Create an Artifact
------------------

.. literalinclude:: ../_scripts/create_example.sh
   :language: bash

Artifact GET Response::

    {
        "pulp_created": "2019-05-16T20:07:48.066089Z",
        "pulp_href": "/pulp/api/v3/artifacts/cff8078a-826f-4f7e-930d-422c2f134a07/",
        "file": "artifact/97/144ab16c9aa0e6072d471d6aebe7c21083e21359137e676445bfeb4051ba25",
        "md5": "5148c996f375ed5aab94ef6993df90a0",
        "sha1": "a7bd2bcaf1d68505f3e8b2cfe3505d01b31db306",
        "sha224": "18a167922b68a3fb8f2d9a71fa78f9776f5402dce4b3d97d5cea2559",
        "sha256": "97144ab16c9aa0e6072d471d6aebe7c21083e21359137e676445bfeb4051ba25",
        "sha384": "4cd006bfac7f2e41baa8c411536579b134daeb3ad666310d21463f384a7020360703fc5538b4eca724033498d514e144",
        "sha512": "e1aae6bbc6fd24cf890b82ffa824629518e6e93935935a0b7c008fbd9fa59f08aa32a7d8580b31a65b21caa0f48e737d8e555eaa777912bea5772799f64a2dd4",
        "size": 11
    }

Reference (pulpcore): `Artifact API Usage
<https://docs.pulpproject.org/restapi.html#tag/artifacts>`_

Create a Containerfile
----------------------

.. literalinclude:: ../_scripts/create_containerfile.sh
   :language: bash

Build an OCI image
------------------

.. literalinclude:: ../_scripts/build_containerfile.sh
   :language: bash

.. _push-workflow:

Push content to a Repository
=============================

Users can push container image to the reposities hosted by Container Registry

.. note::
   If token auth is enabled admin credentials will be required during push operation.
   Provide them in the login to the registry or in each API call.
   
::

        $ podman tag d21d863f69b5 localhost:24817/test/this:mytag1.8
        $ push d21d863f69b5 localhost:24817/test/this:mytag1.8
          Getting image source signatures
          Copying blob 210dda196ec1 done
          Copying config d21d863f69 done
          Writing manifest to image destination
          Storing signatures
        
        $ http GET $BASE_ADDR/v2/test/this/tags/list
          HTTP/1.1 200 OK
          Allow: GET, HEAD, OPTIONS
          Connection: close
          Content-Length: 40
          Content-Type: application/json
          Date: Wed, 03 Jun 2020 18:25:46 GMT
          Docker-Distribution-API-Version: registry/2.0
          Server: gunicorn/20.0.4
          Vary: Accept
          X-Frame-Options: SAMEORIGIN

          {
            "name": "test/this",
            "tags": [
                "mytag1.8"
            ]
          }


.. note::
   Content is pushed to a push repository type. A push repository supports neither mirroring of the
   remote content nor addition or removal of the content via Pulp API.

.. note::
   Rollback to the previous repository versions is not possible with a push repository. Its latest version will always be served.

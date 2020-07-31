.. _push-workflow:

Push content to a Repository
=============================

Users can push container image to the reposities hosted by Container Registry
Push API is provided as a tech preview in Pulp Container 2.0.
Functionality may not fully work and backwards compatibility when upgrading to future Pulp Container releases is not guaranteed::

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


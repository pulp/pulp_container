.. _verify-images:

Configure Client Signature Verification Policy
==============================================

In order to verify container images consumed from Pulp Container Registry the following files need
to be configured on the client side:

* ``/etc/containers/registries.d/default.yaml``

This is a default registries.d configuration file.  You may add to this file or create additional
files in registries.d/.

For full details and spec refer to https://github.com/containers/image/blob/main/docs/containers-registries.d.5.md

Provide a read and write location for a separate ``sigstore`` for the registry in question.
Pulp Container Registry has an integrated signature store, therefore there is no need to provide any
updates to this file. The client will try to use the registry extentions API to read and write image
signatures.

* ``/etc/containers/policy.json``

This is a default signature verification policy file that is used to specify the policy,
e.g. trusted keys, applicable when deciding whether to accept an image, or individual signatures
of that image, as valid.

Parsing this json file is performed in a strict manner: unrecognized, duplicated or otherwise
invalid fields cause the entire file, and usually the entire operation, to be rejected.

For full details and spec refer to https://github.com/containers/image/blob/main/docs/containers-policy.json.5.md


Verify Images Mirrored with its Original Signature
--------------------------------------------------

Use case: Pulp Container Registy contains mirrored container images and their signatures from
a remote registry.


Given that there is already a container repo created, create a remote and specify the url to sync
container images from and sigstore url to fetch and store locally their corresponding original
signatures.

::

        $ http POST https://fluffy.example.com/pulp/api/v3/remotes/container/container/ name=legacy-registry-rh url=https://registry.access.redhat.com upstream_name=ubi8/ubi-micro sigstore=https://access.redhat.com/webassets/docker/content/sigstore include_tags:=[\"8.5\"]
        HTTP/1.1 201 Created
        Access-Control-Expose-Headers: Correlation-ID
        Allow: GET, POST, HEAD, OPTIONS
        Connection: keep-alive
        Content-Length: 697
        Content-Type: application/json
        Correlation-ID: f488df2618814ba3a8a073c433bdf642
        Date: Thu, 10 Mar 2022 15:06:02 GMT
        Location: /pulp/api/v3/remotes/container/container/64da87b6-7bff-4ab5-9b35-7922e3efd352/
        Referrer-Policy: same-origin
        Server: nginx/1.20.1
        Strict-Transport-Security: max-age=15768000
        Vary: Accept, Cookie
        X-Content-Type-Options: nosniff
        X-Frame-Options: DENY

        {
            "ca_cert": null,
            "client_cert": null,
            "connect_timeout": null,
            "download_concurrency": null,
            "exclude_tags": null,
            "headers": null,
            "include_tags": [
                "8.5"
            ],
            "max_retries": null,
            "name": "legacy-registry-rh",
            "policy": "immediate",
            "proxy_url": null,
            "pulp_created": "2022-03-10T15:06:02.107728Z",
            "pulp_href": "/pulp/api/v3/remotes/container/container/64da87b6-7bff-4ab5-9b35-7922e3efd352/",
            "pulp_labels": {},
            "pulp_last_updated": "2022-03-10T15:06:02.107769Z",
            "rate_limit": null,
            "sigstore": "https://access.redhat.com/webassets/docker/content/sigstore",
            "sock_connect_timeout": null,
            "sock_read_timeout": null,
            "tls_validation": true,
            "total_timeout": null,
            "upstream_name": "ubi8/ubi-micro",
            "url": "https://registry.access.redhat.com"
        }

Trigger a sync repo task using this remote.

.. note::
   Some registries have an integrated signature store. In such case there is no need to provide
   the signature url on the remote. Pulp will automatically discover the integrated signature store
   capability of the remote registry and will mirror signatures alonside with images.

After sync task completion, create distribution with the base_path ``local-ubi8-repo`` under which
the image and signatures will be available for pull and verification:

::

        $ http https://fluffy.example.com/pulp/api/v3/distributions/container/container/1e59e5a8-5247-401d-a9b5-9b3ef07d5efe/
        HTTP/1.1 200 OK
        Access-Control-Expose-Headers: Correlation-ID
        Allow: GET, PUT, PATCH, DELETE, HEAD, OPTIONS
        Connection: keep-alive
        Content-Length: 659
        Content-Type: application/json
        Correlation-ID: ab2d64376e2849c5bc0cd1f999355115
        Date: Thu, 10 Mar 2022 16:08:25 GMT
        Referrer-Policy: same-origin
        Server: nginx/1.20.1
        Strict-Transport-Security: max-age=15768000
        Vary: Accept, Cookie
        X-Content-Type-Options: nosniff
        X-Frame-Options: DENY

        {
            "base_path": "local-ubi8-repo",
            "content_guard": "/pulp/api/v3/contentguards/core/content_redirect/27d55db4-2b99-49f6-9838-8ca52647d714/",
            "description": null,
            "name": "local-ubi8-repo",
            "namespace": "/pulp/api/v3/pulp_container/namespaces/fe4d8115-a81c-4eb3-950e-2cf1cc7f033f/",
            "private": false,
            "pulp_created": "2022-03-10T16:04:52.026832Z",
            "pulp_href": "/pulp/api/v3/distributions/container/container/1e59e5a8-5247-401d-a9b5-9b3ef07d5efe/",
            "pulp_labels": {},
            "registry_path": "fluffy.example.com/local-ubi8-repo",
            "repository": null,
            "repository_version": "/pulp/api/v3/repositories/container/container/60747422-30d8-4b92-83e6-e6f025b6d829/versions/1/"
        }

Since the original singed identity differs from the location the images are being served,
the ``remapIdentity`` and full registry path prefix needs to be specified.

::

        $ cat /etc/containers/policy.json
        {
          "default": [{"type": "reject"}],
          "transports": {
            "docker": {
              "fluffy.example.com/local-ubi8-repo": [
                {
                  "type": "signedBy",
                  "keyType": "GPGKeys",
                  "keyPath": "/path-to-rh-key.txt",
                  "signedIdentity": {
                      "type": "remapIdentity",
                      "prefix": "fluffy.example.com/local-ubi8-repo",
                      "signedPrefix": "registry.access.redhat.com/ubi8/ubi-micro"
                  }
                }
              ]
            },
            "containers-storage": {
            "": [{"type": "insecureAcceptAnything"}] /* Allow copy operations on any images stored in containers storage (e.g. podman push) */
            }
          }
        }


       podman pull fluffy.example.com/local-ubi8-repo:8.5


Verify Images Pushed into the Registry
--------------------------------------

Use case: Pulp Container Registry serves container images that were pushed into it (signed or not).

Push an image into Pulp Container registry and sign it in one go:

::

        $ podman push fluffy.example.com/myrepo/test-image:foo --sign-by pupsik@redhat.com
        Copying blob 252fdf0c3b6a done  
        Copying config 829374d342 done  
        Writing manifest to image destination
        Signing manifest
        Storing signatures

        $ podman pull fluffy.example.com/myrepo/test-image:foo 
        Trying to pull fluffy.example.com/myrepo/test-image:foo...
        Getting image source signatures
        Checking if image destination supports signatures
        Copying blob 58147e24f776 skipped: already exists  
        Copying config 829374d342 done  
        Writing manifest to image destination
        Storing signatures
        829374d342ae65a12f3a95911bc04a001894349f70783fda841b1a784008727d


        $ cat  /etc/containers/policy.json
        {
          "default": [{"type": "reject"}],
          "transports": {
            "docker": {
               "fluffy.example.com": [
                {
                  "type": "signedBy",
                  "keyType": "GPGKeys",
                  "keyPath": "/path-to-pupsik-key.gpg"
                }
              ]
            },
            "containers-storage": {
            "": [{"type": "insecureAcceptAnything"}] /* Allow copy operations on any images stored in containers storage (e.g. podman push) */
            }
          }
        }


Verify Images from Multiple Registries
--------------------------------------

Use case: Pull and verify content from Pulp Container registry and also other registries.

To pull and verify images coming also from ``registry.access.redhat.com`` create a separate
signature store configuration file for it:

::

        $ cat  /etc/containers/registries.d/rh-legacy-registry.yaml
        docker:
         registry.access.redhat.com:
                 sigstore: https://access.redhat.com/webassets/docker/content/sigstore


        $ podman pull registry.access.redhat.com/ubi7/ubi:7.9
        Trying to pull registry.access.redhat.com/ubi7/ubi:7.9...
        Getting image source signatures
        Checking if image destination supports signatures
        Copying blob a2745c55c3c1 done
        Copying blob fd3cd11aea08 done
        Copying config 873e1c048b done
        Writing manifest to image destination
        Storing signatures
        873e1c048bf84592ae377f21515961eba5ea20c47223bc890356c680409ef7f1

        $ cat  /etc/containers/policy.json


        {
          "default": [{"type": "reject"}],
          "transports": {
            "docker": {
              "fluffy.example.com/local-ubi8-repo": [
                {
                  "type": "signedBy",
                  "keyType": "GPGKeys",
                  "keyPath": "/path-to-rh-key.txt",
                  "signedIdentity": {
                      "type": "remapIdentity",
                      "prefix": "fluffy.example.com/local-ubi8-repo",
                      "signedPrefix": "registry.access.redhat.com/ubi8/ubi-micro"
                  }
                }
              ],
               "fluffy.example.com": [
                {
                  "type": "signedBy",
                  "keyType": "GPGKeys",
                  "keyPath": "/path-to-pupsik-key.gpg"
                }
               ],
               "registry.access.redhat.com": [
                {
                  "type": "signedBy",
                  "keyType": "GPGKeys",
                  "keyPath": "/path-to-rh-key.txt"
                }
              ]
            },
            "containers-storage": {
            "": [{"type": "insecureAcceptAnything"}] /* Allow copy operations on any images stored in containers storage (e.g. podman push) */
            }
          }
        }

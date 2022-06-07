.. _sign-images:

Image Signature Configuration
=============================

Administrators can add a container manifest signing service to The Pulp Registry using the command
line tools. Users may then associate the signing service with container repositories.
The example below demonstrates how a manifest signing service can be created using ``gpg``:

1. Make sure the service user ``pulp`` has access to ``gpg`` and that the key pair is
   installed in its key rings. The private key might alternatively be provided by a
   hardware cryptographic device.

2. Create a signing script that accepts a manifest path as the only argument. The script invokes
   ``skopeo standalone-sign`` command that generates a container signature for the image manifest,
   using the key specified via the ``PULP_SIGNING_KEY_FINGERPRINT`` environment variable. The script
   should then print out a JSON structure with the following format. The path of the created
   signature is a relative path inside the current working directory::

       {"signature_path": "signature"}

   Below is a snippet of the signing script to be used for signing content:

   .. code-block:: bash

       #!/usr/bin/env bash

        MANIFEST_PATH=$1
        FINGEPRINT="$PULP_SIGNING_KEY_FINGERPRINT"
        IMAGE_REFERENCE="$REFERENCE"
        SIGNATURE_PATH="$SIG_PATH"

        # Create container signature
        skopeo standalone-sign $MANIFEST_PATH $IMAGE_REFERENCE $FINGEPRINT --output $SIGNATURE_PATH
        # Check the exit status
        STATUS=$?
        if [ $STATUS -eq 0 ]; then
          echo {\"signature_path\": \"$SIGNATURE_PATH\"}
        else
          exit $STATUS
        fi

   .. note::

       Make sure the script contains a proper shebang and Pulp has got valid permissions
       to execute it.
       Since the script invokes a ``skopeo`` command, it should be installed as well.
       Environment variables passed to the script cannot be changed since these are the
       variables expected by the signing facility.

   .. note:: 
   
      If the GPG key is password protected the password must be stored in a text file and
      the path passed to skopeo `--passphrase-file` argument.

3. Create a signing service consisting of an absolute path to the script and a meaningful
   name describing the script's purpose. It is possible to create a signing service by using the
   ``pulpcore-manager add-signing-service`` command::

       $ pulpcore-manager add-signing-service signing-service-test /var/lib/pulp/scripts/bash-script.sh 45ACE14E3EBB9BBA --class container:ManifestSigningService

   .. note::

       While creating a signing service, the container model ``ManifestSigningService``
       runs additional checks in order to prevent saving invalid scripts to the database.
       This feature enables administrators to validate their signing scripts in advance.

4. Retrieve and check the saved signing service via REST API::

	$ http GET https://pulp.example.com/pulp/api/v3/signing-services/187120de-307e-4389-b17d-9e42ab295151/

	{
	    "name": "signing-service-test",
	    "pubkey_fingerprint": "8F336A705074623F7FC3273945ACE14E3EBB9BBA",
	    "public_key": "-----BEGIN PGP PUBLIC KEY BLOCK-----\n\...snip...\n-----END PGP PUBLIC KEY BLOCK-----\n",
	    "pulp_created": "2022-01-04T16:51:49.208122Z",
	    "pulp_href": "/pulp/api/v3/signing-services/187120de-307e-4389-b17d-9e42ab295151/",
	    "script": "/var/lib/pulp/scripts/bash-script.sh "
	}

Afterwards, users are able to sign selected content by the provided script.


Sign Images Pushed to the Registry
==================================

Given that an image is pushed to the Pulp Registry via ``podman/docker push`` or via the standard
DockerRegistry v2 push API, a repository is created containing it::

      $ http GET https://pulp.example.com/pulp/api/v3/repositories/container/container-push/
        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "description": null,
                    "latest_version_href": "/pulp/api/v3/repositories/container/container-push/3b279a32-b313-44bf-ad41-4359a92cae24/versions/9/",
                    "manifest_signing_service": null,
                    "name": "test/minio",
                    "pulp_created": "2021-12-10T20:38:40.379570Z",
                    "pulp_href": "/pulp/api/v3/repositories/container/container-push/3b279a32-b313-44bf-ad41-4359a92cae24/",
                    "pulp_labels": {},
                    "retain_repo_versions": null,
                    "versions_href": "/pulp/api/v3/repositories/container/container-push/3b279a32-b313-44bf-ad41-4359a92cae24/versions/"
                }
            ]
        }

Trigger ``sign`` task to sign previously pushed image into the repository. One can associate
``manifest_signing_service`` with the repository which will be used automatically during sign
operation or it can be explictly specified in the following manner::

       $ http https://pulp.example.com/pulp/api/v3/repositories/container/container-push/3b279a32-b313-44bf-ad41-4359a92cae24/sign/ manifest_signing_service=/pulp/api/v3/signing-services/187120de-307e-4389-b17d-9e42ab295151/
         {
             "task": "/pulp/api/v3/tasks/2d6eb9b7-f5aa-40b5-be1c-99c40805d049/"
         }


       $ http GET https://pulp.example.com/pulp/api/v3/tasks/2d6eb9b7-f5aa-40b5-be1c-99c40805d049/
         {
             "child_tasks": [],
             "created_resources": [
                 "/pulp/api/v3/repositories/container/container-push/3b279a32-b313-44bf-ad41-4359a92cae24/versions/10/"
             ],
             "error": null,
             "finished_at": "2021-12-10T20:39:57.016883Z",
             "logging_cid": "f397ba767a9649b68fee8fe90826e1e7",
             "name": "pulp_container.app.tasks.sign.sign",
             "parent_task": null,
             "progress_reports": [],
             "pulp_created": "2021-12-10T20:39:56.741507Z",
             "pulp_href": "/pulp/api/v3/tasks/2d6eb9b7-f5aa-40b5-be1c-99c40805d049/",
             "reserved_resources_record": [
                 "/pulp/api/v3/repositories/container/container-push/3b279a32-b313-44bf-ad41-4359a92cae24/"
             ],
             "started_at": "2021-12-10T20:39:56.780215Z",
             "state": "completed",
             "task_group": null,
             "worker": "/pulp/api/v3/workers/eb65c2d9-31b2-47dc-847e-dad0e744c539/"
         }

Upon task complection, a signature is created and added to the repository::

      $ http GET https://pulp.example.com/pulp/api/v3/repositories/container/container-push/3b279a32-b313-44bf-ad41-4359a92cae24/versions/10/
        {
            "base_version": null,
            "content_summary": {
                "added": {
                    "container.signature": {
                        "count": 1,
                        "href": "/pulp/api/v3/content/container/signatures/?repository_version_added=/pulp/api/v3/repositories/container/container-push/3b279a32-b313-44bf-ad41-4359a92cae24/versions/10/"
                    }
                },
                "present": {
                    "container.blob": {
                        "count": 8,
                        "href": "/pulp/api/v3/content/container/blobs/?repository_version=/pulp/api/v3/repositories/container/container-push/3b279a32-b313-44bf-ad41-4359a92cae24/versions/10/"
                    },
                    "container.manifest": {
                        "count": 1,
                        "href": "/pulp/api/v3/content/container/manifests/?repository_version=/pulp/api/v3/repositories/container/container-push/3b279a32-b313-44bf-ad41-4359a92cae24/versions/10/"
                    },
                    "container.signature": {
                        "count": 1,
                        "href": "/pulp/api/v3/content/container/signatures/?repository_version=/pulp/api/v3/repositories/container/container-push/3b279a32-b313-44bf-ad41-4359a92cae24/versions/10/"
                    },
                    "container.tag": {
                        "count": 1,
                        "href": "/pulp/api/v3/content/container/tags/?repository_version=/pulp/api/v3/repositories/container/container-push/3b279a32-b313-44bf-ad41-4359a92cae24/versions/10/"
                    }
                },
                "removed": {}
            },
            "number": 10,
            "pulp_created": "2021-12-10T20:39:56.942014Z",
            "pulp_href": "/pulp/api/v3/repositories/container/container-push/3b279a32-b313-44bf-ad41-4359a92cae24/versions/10/",
            "repository": "/pulp/api/v3/repositories/container/container-push/3b279a32-b313-44bf-ad41-4359a92cae24/"
        }


        $ http GET https://pulp.example.com/pulp/api/v3/content/container/signatures/?repository_version=/pulp/api/v3/repositories/container/container-push/3b279a32-b313-44bf-ad41-4359a92cae24/versions/10/

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "creator": "atomic 5.16.2-dev",
                    "digest": "sha256:2d916bd0c131e9da11d09a8490a4529cf8fd5b3063b093a2ce115c45d8564c4a",
                    "key_id": "45ACE14E3EBB9BBA",
                    "name": "sha256:de0b3821d652af121ad384b0198dc1c6926f77531d6c250cecff3c42d29c95ce@2d916bd0c131e9da11d09a8490a4529c",
                    "pulp_created": "2021-12-10T20:39:56.933134Z",
                    "pulp_href": "/pulp/api/v3/content/container/signatures/365af055-320b-4e19-8cd9-7a3fcaa620d2/",
                    "signed_manifest": "/pulp/api/v3/content/container/manifests/51caa6c9-5c93-4843-9488-c01de3effdf3/",
                    "timestamp": 1639168796,
                    "type": "atomic"
                }
            ]
        }


Sign Images Mirrored into the Registry
======================================

It is possible to sign content that was synchronized from remote registries.
If the content was synced together with signatures, upon signing task completion new signatures will be
added and the original ones will be kept intact::

       $ http https://pulp.example.com/pulp/api/v3/repositories/container/container/2629ca48-1d98-4ce1-88f2-accf2de9de95/versions/1/

        {
            "base_version": null,
            "content_summary": {
                "added": {
                    "container.blob": {
                        "count": 9,
                        "href": "/pulp/api/v3/content/container/blobs/?repository_version_added=/pulp/api/v3/repositories/container/container/2629ca48-1d98-4ce1-88f2-accf2de9de95/versions/1/"
                    },
                    "container.manifest": {
                        "count": 5,
                        "href": "/pulp/api/v3/content/container/manifests/?repository_version_added=/pulp/api/v3/repositories/container/container/2629ca48-1d98-4ce1-88f2-accf2de9de95/versions/1/"
                    },
                    "container.tag": {
                        "count": 2,
                        "href": "/pulp/api/v3/content/container/tags/?repository_version_added=/pulp/api/v3/repositories/container/container/2629ca48-1d98-4ce1-88f2-accf2de9de95/versions/1/"
                    }
                },
                "present": {
                    "container.blob": {
                        "count": 9,
                        "href": "/pulp/api/v3/content/container/blobs/?repository_version=/pulp/api/v3/repositories/container/container/2629ca48-1d98-4ce1-88f2-accf2de9de95/versions/1/"
                    },
                    "container.manifest": {
                        "count": 5,
                        "href": "/pulp/api/v3/content/container/manifests/?repository_version=/pulp/api/v3/repositories/container/container/2629ca48-1d98-4ce1-88f2-accf2de9de95/versions/1/"
                    },
                    "container.tag": {
                        "count": 2,
                        "href": "/pulp/api/v3/content/container/tags/?repository_version=/pulp/api/v3/repositories/container/container/2629ca48-1d98-4ce1-88f2-accf2de9de95/versions/1/"
                    }
                },
                "removed": {}
            },
            "number": 1,
            "pulp_created": "2022-01-04T19:23:03.899602Z",
            "pulp_href": "/pulp/api/v3/repositories/container/container/2629ca48-1d98-4ce1-88f2-accf2de9de95/versions/1/",
            "repository": "/pulp/api/v3/repositories/container/container/2629ca48-1d98-4ce1-88f2-accf2de9de95/"
        }

In order to adhere to the `container signature specs <https://github.com/containers/image/blob/main/docs/containers-signature.5.md>`_,
``future_base_path`` needs to be provided to the sign call. This information will be used in the
signature's ``identity``. It is crucial that ``future_base_path`` matches the  ``base_path`` of the
existing distribution or a future one, under which it is planned to make the content available to the
clients. If the information does not match, the client's policy might reject images on pull
operation. Please refer more to the  `containers.policy specs <https://github.com/containers/image/blob/main/docs/containers-policy.json.5.md>`_.::

        $ http https://pulp.example.com/pulp/api/v3/repositories/container/container/2629ca48-1d98-4ce1-88f2-accf2de9de95/sign/ manifest_signing_service=/pulp/api/v3/signing-services/fe61ee1b-3354-4c11-ab08-b58f53eb2335/ future_base_path=library/busybox

        {
            "task": "/pulp/api/v3/tasks/f20139e2-d76e-4e69-877f-129bf135c475/"
        }


        $ http https://pulp.example.com/pulp/api/v3/repositories/container/container/6508bcfb-9f3d-4caa-af25-07703f832c46/versions/2/

        {
            "base_version": null,
            "content_summary": {
                "added": {
                    "container.signature": {
                        "count": 4,
                        "href": "/pulp/api/v3/content/container/signatures/?repository_version_added=/pulp/api/v3/repositories/container/container/6508bcfb-9f3d-4caa-af25-07703f832c46/versions/2/"
                    }
                },
                "present": {
                    "container.blob": {
                        "count": 9,
                        "href": "/pulp/api/v3/content/container/blobs/?repository_version=/pulp/api/v3/repositories/container/container/6508bcfb-9f3d-4caa-af25-07703f832c46/versions/2/"
                    },
                    "container.manifest": {
                        "count": 5,
                        "href": "/pulp/api/v3/content/container/manifests/?repository_version=/pulp/api/v3/repositories/container/container/6508bcfb-9f3d-4caa-af25-07703f832c46/versions/2/"
                    },
                    "container.signature": {
                        "count": 4,
                        "href": "/pulp/api/v3/content/container/signatures/?repository_version=/pulp/api/v3/repositories/container/container/6508bcfb-9f3d-4caa-af25-07703f832c46/versions/2/"
                    },
                    "container.tag": {
                        "count": 2,
                        "href": "/pulp/api/v3/content/container/tags/?repository_version=/pulp/api/v3/repositories/container/container/6508bcfb-9f3d-4caa-af25-07703f832c46/versions/2/"
                    }
                },
                "removed": {}
            },
            "number": 2,
            "pulp_created": "2022-01-04T21:11:07.080160Z",
            "pulp_href": "/pulp/api/v3/repositories/container/container/6508bcfb-9f3d-4caa-af25-07703f832c46/versions/2/",
            "repository": "/pulp/api/v3/repositories/container/container/6508bcfb-9f3d-4caa-af25-07703f832c46/"
        }

Upon task completion, signatures for every image manifest will be created and added to the repo.
It is possible to specify a single manifest identified by tag or a list of manifests to sign,
by proviging ``tags_list`` option to the call.
Note that ``manifest lists`` are not signed, instead all the image manifests that manifest lists
contain, are signed.

Manage Signatures via the Extensions API
========================================

This API exposes an endpoint for reading and writing image signatures. Users should configure the
sigstore section in the `registries.d file <https://github.com/containers/image/blob/main/docs/containers-registries.d.5.md>`_
accordingly to benefit from the API.

Reading Image Signatures
------------------------

To read existing signatures, issue the following GET request::

    $ http GET http://localhost:24817/extensions/v2/<namespace>/<name>/signatures/sha256:<manifest-digest>

Signatures are retrieved by container clients automatically if the policy requires so. The policy is
defined in the file ``/etc/containers/policy.json``.

Writing Image Signatures
------------------------

To add a new signature to an image, execute the following PUT request::

    $ http PUT http://localhost:24817/extensions/v2/<namespace>/<name>/signatures/sha256:<manifest-digest> < signature.json

The JSON payload has the same structure as described in the `container signature specs <https://github.com/containers/image/blob/main/docs/containers-signature.5.md>`_::

    {
      "schemaVersion": 2,
      "type":    "atomic",
      "name":    "sha256:4028782c08eae4a8c9a28bf661c0a8d1c2fc8e19dbaae2b018b21011197e1484@cddeb7006d914716e2728000746a0b23",
      "content": "<cryptographic_signature>"
    }

This step can be also done via podman or skopeo. After configuring a GPG keyring, it is possible to
issue the following command to push a tagged image altogether with its signature to the Pulp
Registry::

    $ podman push --tls-verify=false --sign-by username@email.com localhost:24817/<namespace>/<name>

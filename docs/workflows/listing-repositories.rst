Listing Repositories
====================

A registry may contain several repositories which hold collections of multiple images. Each
repository is identified by its unique name. The list of names of all distributed repositories
is made available through the ``_catalog`` endpoint.

For instance, let's assume that a new distribution of a repository with the name ``bar`` was
recently created. Its name is now possible to fetch from the list of names of distributed
repositories::

    http :24817/v2/_catalog

    HTTP/1.1 200 OK
    Content-Length: 25
    Content-Type: application/json; charset=utf-8
    Date: Wed, 22 Jan 2020 09:27:16 GMT
    Docker-Distribution-API-Version: registry/2.0
    Server: Python/3.7 aiohttp/3.6.2

    {
        "repositories": [
            "foo",
            "bar"
        ]
    }

.. note::
    For the sake of simplicity, there is missing a part that requires a user to authenticate via
    a Bearer token. The token authentication is enabled by default and does not come pre-configured
    out of the box. An administrator needs to to set up the environment in advance to enable
    users to consume content with authorized access. Lean more at :ref:`authentication`.


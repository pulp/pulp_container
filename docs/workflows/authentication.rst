.. _authentication:

Registry Token Authentication
=============================

Pulp registry supports the `token authentication <https://docs.docker.com/registry/spec/auth/token/>`_.
This enables users to pull content with an authorized access. A token server grants access based on the
user's privileges and current scope.

The feature is enabled by default. However, it is required to define the following settings first:

    - **A fully qualified domain name of a token server**. The token server is responsible for generating
      Bearer tokens. Append the constant ``TOKEN_SERVER`` to the settings file ``pulp_container/app/settings.py``.
    - **A token signature algorithm**. A particular signature algorithm can be chosen only from the list of
      `supported algorithms <https://pyjwt.readthedocs.io/en/latest/algorithms.html#digital-signature-algorithms>`_.
      Pulp uses exclusively asymmetric cryptography to sign and validate tokens. Therefore, it is possible
      only to choose from the algorithms, such as ES256, RS256, or PS256. Append the the constant
      ``TOKEN_SIGNATURE_ALGORITHM`` with a selected algorithm to the settings file.
    - **Paths to secure keys**. These keys are going to be used for a signing and validation of tokens.
      Remember that the keys have to be specified in the **PEM format**. To generate keys, one could use
      the openssl utility. In the following example, the utility is used to generate keys with the algorithm
      ES256.

          1. Generate a private key::

              $ openssl ecparam -genkey -name prime256v1 -noout -out /tmp/private_key.pem

          2. Generate a public key out of the private key::

              $ openssl ec -in /tmp/private_key.pem -pubout -out /tmp/public_key.pem

Below is provided and example of the settings file:

.. code-block:: python

    TOKEN_SERVER = "localhost:24816/token"
    TOKEN_SIGNATURE_ALGORITHM = 'ES256'
    PUBLIC_KEY_PATH = '/tmp/public_key.pem'
    PRIVATE_KEY_PATH = '/tmp/private_key.pem'

To learn more about Pulp settings, take a look at `Configuration
<https://docs.pulpproject.org/en/3.0/nightly/installation/configuration.html>`_.

Restart Pulp services in order to reload the updated settings. Pulp will fetch a domain for the token
server and will initialize all handlers according to that. Check if the token authentication was
successfully configured by initiating the following set of commands in your environment::

    $ http 'http://localhost:24816/v2/'

    HTTP/1.1 401 Access to the requested resource is not authorized. A provided Bearer token is invalid.
    Content-Length: 92
    Content-Type: text/plain; charset=utf-8
    Date: Mon, 14 Oct 2019 16:46:48 GMT
    Docker-Distribution-API-Version: registry/2.0
    Server: Python/3.7 aiohttp/3.6.1
    Www-Authenticate: Bearer realm="http://localhost:24816/token",service="localhost:24816"

    401: Access to the requested resource is not authorized. A provided Bearer token is invalid.

Send a request to a specified realm::

    $ http 'http://localhost:24816/token?service=localhost:24816'

    HTTP/1.1 200 OK
    Content-Length: 566
    Content-Type: application/json; charset=utf-8
    Date: Mon, 14 Oct 2019 16:47:33 GMT
    Server: Python/3.7 aiohttp/3.6.1

    {
        "expires_in": 300,
        "issued_at": "2019-10-14T16:47:33.107118Z",
        "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzI1NiIsImtpZCI6IkhBM1Q6SVlSUjpHUTNUOklPTEM6TVE0RzpFT0xDOkdGUVQ6QVpURTpHQlNXOkNaUlY6TUlZVzpLTkpWIn0.eyJhY2Nlc3MiOlt7InR5cGUiOiIiLCJuYW1lIjoiIiwiYWN0aW9ucyI6W119XSwiYXVkIjoibG9jYWxob3N0OjI0ODE2IiwiZXhwIjoxNTcxMDcxOTUzLCJpYXQiOjE1NzEwNzE2NTMsImlzcyI6ImxvY2FsaG9zdDoyNDgxNi90b2tlbiIsImp0aSI6IjRmYTliYTYwLTY0ZTUtNDA3MC1hMzMyLWZmZTRlMTk2YzVjNyIsIm5iZiI6MTU3MTA3MTY1Mywic3ViIjoiIn0.pirj8yhbjYnldxmZ-jIZ72VJrzxkAnwLXLu1ND9QAL-kl3gZrvPbp98w2xdhEoQ_7WEka4veb6uU5ZzmD87X1Q"
    }

Use the generated token to access the root again::

    $ http 'localhost:24816/v2/' --auth-type=jwt --auth="eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzI1NiIsImtpZCI6IkhBM1Q6SVlSUjpHUTNUOklPTEM6TVE0RzpFT0xDOkdGUVQ6QVpURTpHQlNXOkNaUlY6TUlZVzpLTkpWIn0.eyJhY2Nlc3MiOlt7InR5cGUiOiIiLCJuYW1lIjoiIiwiYWN0aW9ucyI6W119XSwiYXVkIjoibG9jYWxob3N0OjI0ODE2IiwiZXhwIjoxNTcxMDcxOTUzLCJpYXQiOjE1NzEwNzE2NTMsImlzcyI6ImxvY2FsaG9zdDoyNDgxNi90b2tlbiIsImp0aSI6IjRmYTliYTYwLTY0ZTUtNDA3MC1hMzMyLWZmZTRlMTk2YzVjNyIsIm5iZiI6MTU3MTA3MTY1Mywic3ViIjoiIn0.pirj8yhbjYnldxmZ-jIZ72VJrzxkAnwLXLu1ND9QAL-kl3gZrvPbp98w2xdhEoQ_7WEka4veb6uU5ZzmD87X1Q"

    HTTP/1.1 200 OK
    Content-Length: 2
    Content-Type: application/json; charset=utf-8
    Date: Mon, 14 Oct 2019 16:50:26 GMT
    Docker-Distribution-API-Version: registry/2.0
    Server: Python/3.7 aiohttp/3.6.1

    {}

After performing multiple HTTP requests, the root responded with a default value ``{}``. Received
token can be used to access all endpoints within the requested scope too.

Regular container engines, like docker, or podman, can take advantage of the token authentication.
The authentication is handled by the engines as shown before.

.. code-block:: bash

    podman pull localhost:24816/foo/bar

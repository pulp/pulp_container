.. _authentication:

Registry Token Authentication
=============================

Pulp registry supports the `token authentication <https://docs.docker.com/registry/spec/auth/token/>`_.
This enables users to pull/push content with an authorized access. A token server grants access based on the
user's privileges and current scope.

The feature is enabled by default. However, it is possible to disable it from the settings by declaring
``TOKEN_AUTH_DISABLED=True``.

The token authentication requires an administrator to define the following settings:

    - **A fully qualified domain name of a token server with an associated port number**. The token server is
      responsible for generating Bearer tokens. Append the constant ``TOKEN_SERVER`` to the settings file
      ``pulp_container/app/settings.py``.
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

          2. Check if the generated private key has the proposed permissions:

              * mode: 600
              * owner: pulp (the account that pulp runs under)
              * group: pulp (the group of the account that pulp runs under)

          3. Generate a public key out of the private key::

              $ openssl ec -in /tmp/private_key.pem -pubout -out /tmp/public_key.pem

          4. Check if the generated public key has the proposed permissions:

              * mode: 644
              * owner: pulp (the account that pulp runs under)
              * group: pulp (the group of the account that pulp runs under)


In addition to that, the administrator can configure the duration of the validity of issued tokens
via the setting ``TOKEN_EXPIRATION_TIME``. The default expiration time is ``300`` seconds.

Below is provided an example of the settings file:

.. code-block:: python

    TOKEN_SERVER = "http://localhost:24817/token/"
    TOKEN_SIGNATURE_ALGORITHM = 'ES256'
    PUBLIC_KEY_PATH = '/tmp/public_key.pem'
    PRIVATE_KEY_PATH = '/tmp/private_key.pem'

To learn more about Pulp settings, take a look at `Configuration
<https://docs.pulpproject.org/installation/configuration.html>`_.

Restart Pulp services in order to reload the updated settings. Pulp will fetch a domain for the token
server and will initialize all handlers according to that. Check if the token authentication was
successfully configured by initiating the following set of commands in your environment::

    $ http 'http://localhost:24817/v2/'

    HTTP/1.1 401 Unauthorized
    Allow: GET, HEAD, OPTIONS
    Connection: close
    Content-Length: 58
    Content-Type: application/json
    Date: Mon, 13 Jul 2020 09:56:54 GMT
    Docker-Distribution-Api-Version: registry/2.0
    Server: gunicorn/20.0.4
    Vary: Accept
    WWW-Authenticate: Bearer realm="http://localhost:24817/token/",service="pulp3-source-fedora31.localhost.example.com"
    X-Frame-Options: SAMEORIGIN

    {
        "detail": "Authentication credentials were not provided."
    }

Send a request to a specified realm::

    $ http http://localhost:24817/token/?service=pulp3-source-fedora31.localhost.example.com

    HTTP/1.1 200 OK
    Allow: GET, HEAD, OPTIONS
    Connection: close
    Content-Length: 609
    Content-Type: application/json
    Date: Mon, 13 Jul 2020 09:57:25 GMT
    Server: gunicorn/20.0.4
    Vary: Accept, Cookie
    X-Frame-Options: SAMEORIGIN

    {
        "expires_in": 300,
        "issued_at": "2020-07-13T09:57:25.601760Z",
        "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzI1NiIsImtpZCI6IkdNMkQ6SU9CVDpHQVpEOk1aUlE6RzQyVzpDWkJaOkdWUlQ6R00zRzpNRTJUOlFNSlk6R1JURDpNTUpRIn0.eyJhY2Nlc3MiOlt7InR5cGUiOiIiLCJuYW1lIjoiIiwiYWN0aW9ucyI6W119XSwiYXVkIjoicHVscDMtc291cmNlLWZlZG9yYTMxLmxvY2FsaG9zdC5leGFtcGxlLmNvbSIsImV4cCI6MTU5NDYzNDU0NSwiaWF0IjoxNTk0NjM0MjQ1LCJpc3MiOiJodHRwOi8vbG9jYWxob3N0OjI0ODE3L3Rva2VuLyIsImp0aSI6ImU4ZTUyYzVhLWYxMzAtNGJlMi1iNjFhLTUwNzVhMjhkMTA0YSIsIm5iZiI6MTU5NDYzNDI0NSwic3ViIjoiIn0.ySDUHooaURbsyKLkHoXqA1JJPwlcDtpz_u6GgcqA8fmFGmSWJFlAGYtA2GLXDzPioH-bh1JkMJdBDs61c5JnFw"
    }

Use the generated token to access the root again::

    $ http --auth-type=jwt --auth=eyJ0eXAiOiJKV1QiLCJhbGciOiJFUzI1NiIsImtpZCI6IkdNMkQ6SU9CVDpHQVpEOk1aUlE6RzQyVzpDWkJaOkdWUlQ6R00zRzpNRTJUOlFNSlk6R1JURDpNTUpRIn0.eyJhY2Nlc3MiOlt7InR5cGUiOiIiLCJuYW1lIjoiIiwiYWN0aW9ucyI6W119XSwiYXVkIjoicHVscDMtc291cmNlLWZlZG9yYTMxLmxvY2FsaG9zdC5leGFtcGxlLmNvbSIsImV4cCI6MTU5NDYzNDU0NSwiaWF0IjoxNTk0NjM0MjQ1LCJpc3MiOiJodHRwOi8vbG9jYWxob3N0OjI0ODE3L3Rva2VuLyIsImp0aSI6ImU4ZTUyYzVhLWYxMzAtNGJlMi1iNjFhLTUwNzVhMjhkMTA0YSIsIm5iZiI6MTU5NDYzNDI0NSwic3ViIjoiIn0.ySDUHooaURbsyKLkHoXqA1JJPwlcDtpz_u6GgcqA8fmFGmSWJFlAGYtA2GLXDzPioH-bh1JkMJdBDs61c5JnFw :24817/v2/

    HTTP/1.1 200 OK
    Allow: GET, HEAD, OPTIONS
    Connection: close
    Content-Length: 2
    Content-Type: application/json
    Date: Mon, 13 Jul 2020 09:58:40 GMT
    Docker-Distribution-Api-Version: registry/2.0
    Server: gunicorn/20.0.4
    Vary: Accept
    X-Frame-Options: SAMEORIGIN

    {}

After performing multiple HTTP requests, the root responded with a default value ``{}``. Received
token can be used to access all endpoints within the requested scope too.

Regular container engines, like docker, or podman, can take advantage of the token authentication.
The authentication is handled by the engines as shown before.

.. code-block:: bash

    podman pull localhost:24817/foo/bar

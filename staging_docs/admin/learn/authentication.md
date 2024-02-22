# Authentication

The Pulp Registry supports [token authentication](https://distribution.github.io/distribution/spec/auth/token/).
The token authentication is enabled by default and **does not** come pre-configured out of the box. See
the section [Token Authentication](#token-authentication) for more details.

The token authentication can be disabled via the pulp settings by declaring `TOKEN_AUTH_DISABLED=True`.
When disabled, Basic authentication or Remote Webserver authentication is used as a default
authentication method depending on a particular configuration.

## Basic Authentication

Base64 encoded user credentials are passed along with the `Authorization` header with each Registry
API request to Pulp. Container clients handle the authentication procedure automatically.

All users are permitted to pull content from the Registry without any limitations because the concept
of private repositories is not adopted once token authentication is disabled. But, only users with
staff permissions are allowed to push content to the Registry.

## Remote Webserver Authentication

A webserver that sits in front of Pulp (e.g., Nginx or Apache) is a proxy that forwards user
credentials to a remote webserver which authenticates users. For authenticated users, the webserver
sets the header `settings.REMOTE_USER_ENVIRON_NAME` for every request and passes it to Pulp.

Similarly to basic authentication, all users can pull content from the Registry without limitations
and only staff is allowed to push new content to the Registry.

To set up the remote webserver authentication, update the Pulp settings in the following way:

```python
TOKEN_AUTH_DISABLED = True

REMOTE_USER_ENVIRON_NAME = "HTTP_REMOTE_USER"

AUTHENTICATION_BACKENDS = [
    "pulpcore.app.authentication.PulpNoCreateRemoteUserBackend",
    "pulpcore.backends.ObjectRolePermissionBackend",
]
REST_FRAMEWORK__DEFAULT_AUTHENTICATION_CLASSES = (
    "rest_framework.authentication.SessionAuthentication",
    "pulpcore.app.authentication.PulpRemoteUserAuthentication",
)
```

Then, configure Nginx or Apache to proxy the authentication header:

```
location /v2/ {
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Host $http_host;
    # we don't want nginx trying to do something clever with
    # redirects, we set the Host: header above already.
    proxy_redirect off;
    proxy_pass http://pulp-api;
    client_max_body_size 0;
+   proxy_set_header Remote_User $remote_user;
}
```

!!! note

    Ensure that users, who are being authenticated, exist in the Pulp database. User names passed
    via the `settings.REMOTE_USER_ENVIRON_NAME` header must agree with user names stored in the
    database.

## Token Authentication

Token authentication allows users to pull/push content with an authorized access. A token server
grants access based on the user's privileges and current scope.

To configure token authentication, an administrator defines the following settings:

1. **A fully qualified domain name of a token server with an associated port number**. The token server is
  responsible for generating Bearer tokens. Append the constant `TOKEN_SERVER` to the settings file
  `pulp_container/app/settings.py`.

2. **A token signature algorithm**. A particular signature algorithm can be chosen only from the list of
  [supported algorithms](https://pyjwt.readthedocs.io/en/latest/algorithms.html#digital-signature-algorithms).
  Pulp uses exclusively asymmetric cryptography to sign and validate tokens. Therefore, it is possible
  only to choose from the algorithms, such as ES256, RS256, or PS256. Append the the constant
  `TOKEN_SIGNATURE_ALGORITHM` with a selected algorithm to the settings file.

3. **Paths to secure keys**. These keys are going to be used for a signing and validation of tokens.
  Remember that the keys have to be specified in the **PEM format**. To generate keys, one could use
  the openssl utility. In the following example, the utility is used to generate keys with the algorithm
  ES256.

    1. Generate a private key:

        ```
        $ openssl ecparam -genkey -name prime256v1 -noout -out /tmp/private_key.pem
        ```
  
    2. Check if the generated private key has the proposed permissions:

        - mode: 600
        - owner: pulp (the account that pulp runs under)
        - group: pulp (the group of the account that pulp runs under)
    
    3. Generate a public key out of the private key:

        ```
        $ openssl ec -in /tmp/private_key.pem -pubout -out /tmp/public_key.pem
        ```
    
    4. Check if the generated public key has the proposed permissions:

        - mode: 644
        - owner: pulp (the account that pulp runs under)
        - group: pulp (the group of the account that pulp runs under)

In addition to that, the administrator can configure the duration of the validity of issued tokens
via the setting `TOKEN_EXPIRATION_TIME`. The default expiration time is `300` seconds.

Below is provided an example of the settings file:

```python
TOKEN_SERVER = "http://localhost:24817/token/"
TOKEN_SIGNATURE_ALGORITHM = 'ES256'
PUBLIC_KEY_PATH = '/tmp/public_key.pem'
PRIVATE_KEY_PATH = '/tmp/private_key.pem'
```

Restart Pulp services in order to reload the updated settings. Pulp will fetch a domain for the token
server and will initialize all handlers according to that.

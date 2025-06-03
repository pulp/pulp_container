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
superuser permissions are allowed to push content to the Registry.

## Remote Webserver Authentication

A webserver that sits in front of Pulp (e.g., Nginx or Apache) is a proxy that forwards user
credentials to a remote webserver which authenticates users. For authenticated users, the webserver
sets the header `settings.REMOTE_USER_ENVIRON_NAME` for every request and passes it to Pulp.

Similarly to basic authentication, all users can pull content from the Registry without limitations
and only superusers are allowed to push new content to the Registry.

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
TOKEN_SERVER = "https://puffy.example.com/token/"
TOKEN_SIGNATURE_ALGORITHM = 'ES256'
PUBLIC_KEY_PATH = '/tmp/public_key.pem'
PRIVATE_KEY_PATH = '/tmp/private_key.pem'
```

Restart Pulp services in order to reload the updated settings. Pulp will fetch a domain for the token
server and will initialize all handlers according to that.


!!! note

    Standard container tooling clients like podman, skopeo and docker handle token authentication calls on
    behalf of the user during pull and push operations. However, if you would like to debug registry
    access or implement manual registry API calls, here are a few examples of how the token authentication
    works behind the scene.

Access the root registry endpoint to check if the token authentication was successfully configured and enabled:

```bash
    $ http 'https://puffy.example.com/v2/'

    HTTP/1.1 401 Unauthorized
    Allow: GET, HEAD, OPTIONS
    Connection: close
    Content-Length: 58
    Content-Type: application/json
    Date: Mon, 13 Jul 2020 09:56:54 GMT
    Docker-Distribution-Api-Version: registry/2.0
    Server: gunicorn/20.0.4
    Vary: Accept
    WWW-Authenticate: Bearer realm="https://puffy.example.com/token/",service="puffy.example.com"
    X-Frame-Options: SAMEORIGIN

    {
        "detail": "Authentication credentials were not provided."
    }
```

Since the request was not authenticated, the registry returned an HTTP 401 error and in the authentication header
there are details on how to authenticate. This time send the request with the specified realm and service:

```bash
$ http https://puffy.example.com/token/?service=puffy.example.com

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
    "access_token": <TOKEN>,
    "expires_in": 300,
    "issued_at": "2020-07-13T09:57:25.601760Z",
    "token": <TOKEN>
}
```

The token was generated to access registry root endpoint.

```bash
$ http --auth-type=jwt --auth=<TOKEN> https://puffy.example.com/v2/

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
```

In order to access other registry endpoints, like manifests, blobs and tags, the scope needs to be provided
as well. In this context, it will be a specific repository with the according action pull or push.

```bash
$ http https://puffy.example.com/v2/library/azure/tags/list
HTTP/1.1 401 Unauthorized
Access-Control-Expose-Headers: Correlation-ID
Allow: GET, HEAD, OPTIONS
Connection: keep-alive
Content-Length: 106
Content-Type: application/json
Correlation-ID: c4e809f1e290478b8acfd0c9f7be7d00
Cross-Origin-Opener-Policy: same-origin
Date: Fri, 17 May 2024 09:18:33 GMT
Docker-Distribution-Api-Version: registry/2.0
Referrer-Policy: same-origin
Server: nginx
Vary: Accept
WWW-Authenticate: Bearer realm="https://puffy.example.com/token/",service="puffy.example.com",scope="repository:library/azure:pull"
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-Registry-Supports-Signatures: 1

{
    "errors": [
        {
            "code": "UNAUTHORIZED",
            "detail": {},
            "message": "Authentication credentials were not provided."
        }
    ]
}
```

```bash
$ http 'https://puffy.example.com/token/?service=puffy.example.com&scope=repository:library/azure:pull'
HTTP/1.1 200 OK
Access-Control-Expose-Headers: Correlation-ID
Allow: GET, HEAD, OPTIONS
Connection: keep-alive
Content-Length: 1311
Content-Type: application/json
Correlation-ID: 611f0ce122a54509b348ff54d5030c80
Cross-Origin-Opener-Policy: same-origin
Date: Fri, 17 May 2024 09:20:29 GMT
Referrer-Policy: same-origin
Server: nginx
Strict-Transport-Security: max-age=15768000
Vary: Accept
X-Content-Type-Options: nosniff
X-Frame-Options: DENY

{
    "access_token": <TOKEN>,
    "expires_in": 300,
    "issued_at": "2024-05-17T09:20:29.660984Z",
    "token": <TOKEN>
}
```

```bash
$ http https://puffy.example.com/v2/library/azure/tags/list --auth-type=jwt --auth=<TOKEN>
HTTP/1.1 200 OK
Access-Control-Expose-Headers: Correlation-ID
Allow: GET, HEAD, OPTIONS
Connection: keep-alive
Content-Length: 42
Content-Type: application/json
Correlation-ID: b944d8b6b1fc474eada8531776a2609b
Cross-Origin-Opener-Policy: same-origin
Date: Fri, 17 May 2024 09:33:04 GMT
Docker-Distribution-Api-Version: registry/2.0
Referrer-Policy: same-origin
Server: nginx
Strict-Transport-Security: max-age=15768000
Vary: Accept
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-Registry-Supports-Signatures: 1

{
    "name": "library/azure",
    "tags": [
        "latest"
    ]
}
```

!!! note

    If the repository is private, one needs to provide basic auth credentials while
    requesting the token in order to pull content from it. If no basic auth is provided,
    then the generated token is for the anonymous user.
    In order to push content to the registry a user always needs to be authenticated.

```bash
$ http 'https://puffy.example.com/token/?service=puffy.example.com&scope=repository:private/azure:pull' --auth-type=basic --auth=alice:wonderland
```

!!! note

    Some registry endpoints, like ``_catalog`` endpoint, are not opened to anonymous/not logged-in users and
    require credentials provided during the token request. Anonymous tokens will still lead to HTTP 401 insufficient scope errors.

```bash
http 'https://puffy.example.com/token/?service=puffy.example.com&scope=registry:catalog:*' --auth-type=basic --auth=alice:wonderland
```

This token embeds permissions that allow to see only those repositories that Alice has access to. 

```bash
$ http https://puffy.example.com/v2/_catalog --auth-type=jwt --auth=<TOKEN>
HTTP/1.1 200 OK
Access-Control-Expose-Headers: Correlation-ID
Allow: GET, HEAD, OPTIONS
Connection: keep-alive
Content-Length: 63
Content-Type: application/json
Correlation-ID: f4ea6c26bcb7462099c0d5757178f7ca
Cross-Origin-Opener-Policy: same-origin
Date: Fri, 17 May 2024 09:57:11 GMT
Docker-Distribution-Api-Version: registry/2.0
Referrer-Policy: same-origin
Server: nginx
Strict-Transport-Security: max-age=15768000
Vary: Accept
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-Registry-Supports-Signatures: 1

{
    "repositories": [
        "alice/azure",
        "alice/openstack-cron"
    ]
}
```

If you are still unsure why you are geting HTTP 401 errors with the generated token, paste its payload to https://jwt.io/
and it will help identify whether the token contains the needed access.

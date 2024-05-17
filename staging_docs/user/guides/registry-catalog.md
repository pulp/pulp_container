# Registry catalog

A registry may contain several repositories which hold collections of multiple images. Each
repository is identified by its unique name. The list of names of all distributed repositories
is made available through the ``_catalog`` endpoint.

For instance, let's assume that a new distribution of a repository with the name ``library/zoo``
was recently created. Its name is now possible to fetch from the list of names of distributed
repositories.

```bash
$ http https://puffy.example.com/v2/_catalog
HTTP/1.1 200 OK
Access-Control-Expose-Headers: Correlation-ID
Allow: GET, HEAD, OPTIONS
Connection: keep-alive
Content-Length: 63
Content-Type: application/json
Correlation-ID: 1de33d4807a244f1b00c10df3fdc7a1b
Cross-Origin-Opener-Policy: same-origin
Date: Fri, 17 May 2024 10:20:25 GMT
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
        "library/zoo",
        "alice/azure",
    ]
}
```
!!! note
    For the sake of simplicity of this example, there is missing required user token authentication
    to this endpoint. Users will see only those repositories in the registry catalog that they have access to.
    Visit [Token authentication section](site:pulp_container/docs/admin/learn/authentication.md) to learn more.

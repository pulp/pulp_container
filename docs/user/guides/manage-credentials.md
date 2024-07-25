# Manage Credentials

Registry's credentials may be stored in a separate file. At the moment, Pulp does not provide
support for reading from this file. Therefore, a user who wants to synchronize content from
a registry, which requires the authentication, he or she has to manually extract data from this
file and pass it directly to Pulp.

!!! note

    A file which contains registry's credentials is also called a pull secret. These terms are
    considered interchangeable.


When using `podman`, the default path for such a file is
`${XDG_RUNTIME_DIR}/containers/auth.json`. The file can have the following content:

```
cat ${XDG_RUNTIME_DIR}/containers/auth.json
{
        "auths": {
                "registry.hub.docker.com": {
                        "auth": "YWRtaW46cGFzc3dvcmQ="
                }
        }
}
```

The content of the file is usually updated by running `podman login ${REGISTRY}` and providing a
valid username and password for the registry `${REGISTRY}`.

!!! note

    In some cases, a pull secret is handled by a registry's maintainer and it is not stored locally
    by default. If so, it is necessary to download it
    (e.g. from <https://access.redhat.com/terms-based-registry/>).


Suppose a user wants to retrieve credentials from the file shown above in order to sync the content.
First, the user retrieves the field `auth`:

```
export AUTH=$(cat ${XDG_RUNTIME_DIR}/containers/auth.json \
    | jq -r '.auths["registry.hub.docker.com"].auth')
```

Then, he or she fetches the username and password by running:

```
read USERNAME PASSWORD <<< $(echo $AUTH | base64 -d | awk -F':' '{print $1, $2}')
```

And finally, the user creates a new Pulp remote, for example, by executing:

```
http POST http://localhost:24817/pulp/api/v3/remotes/container/container/ \
    name='foo/bar' upstream_name='foo/bar' url='https://registry.hub.docker.com' \
    policy='immediate' username=$USERNAME password=$PASSWORD
```

The remote is used by the sync machinery afterwards. Refer to [Mirror and Host Content](site:pulp_container/docs/user/tutorials/01-sync-and-host) if you missed the syncing part.

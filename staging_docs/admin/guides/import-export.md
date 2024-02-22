# Export and Import Images

When maintaining an **air-gapped** environment, one can benefit from using the import/export
machinery. A common workflow usually resembles the following steps:

1. **An administrator exports Pulp's content on a system with the internet connectivity.** The
   system runs a Pulp instance that syncs content from remote repositories.
2. **The exported content (tarball) is moved to another (air-gapped) system.** The transfer can
   be made through the intranet or via an external hard drive.
3. **The administrator imports the exported content by initiating an import task.** The
   procedure takes care of importing the content to another Pulp instance running in the air-gapped
   environment.

## Exporting a Repository

To export a repository, run the following set of commands:

```bash
podman pull ghcr.io/pulp/test-fixture-1:manifest_a

# push a tagged image to the registry
podman login ${REGISTRY_ADDR} -u admin -p password --tls-verify=false
podman tag ghcr.io/pulp/test-fixture-1:manifest_a \
  ${REGISTRY_ADDR}/test/fixture:manifest_a
podman push ${REGISTRY_ADDR}/test/fixture:manifest_a --tls-verify=false

# a repository of the push type is automatically created
REPOSITORY_HREF=$(pulp container repository -t push show \
  --name "test/fixture" | jq -r ".pulp_href")

# export the repository to the directory '/tmp/exports/test-fixture'
EXPORTER_HREF=$(http ${BASE_ADDR}/pulp/api/v3/exporters/core/pulp/ \
  name=both repositories:="[\"${REPOSITORY_HREF}\"]" \
  path=/tmp/exports/test-fixture | jq -r ".pulp_href")
```

If the exported content is no longer needed to be managed on the system, delete it:

```bash
pulp container distribution destroy --name "test/fixture"
pulp orphan cleanup --protection-time 0
```

## Importing the Repository

Import the exported content by running the next commands and monitor the task:

```bash
http ${BASE_ADDR}/pulp/api/v3/repositories/container/container/ \
  name="test/fixture" | jq -r ".pulp_href"

# import the exported repository stored in '/tmp/exports/test-fixture'
IMPORTER_HREF=$(http ${BASE_ADDR}/pulp/api/v3/importers/core/pulp/ \
  name="test/fixture" | jq -r ".pulp_href")
EXPORTED_REPO_PATH=$(find "/tmp/exports/test-fixture" -type f -name \
  "*.tar.gz" | head -n 1)
GROUP_HREF=$(http ${BASE_ADDR}${IMPORTER_HREF}imports/ \
  path=${EXPORTED_REPO_PATH} | jq -r ".task_group")
```

!!! note

    Pass `create_repositories=True` to the `http POST ${BASE_ADDR}${IMPORTER_HREF}imports/`
    request to tell Pulp to create missing repositories during the import procedure on the fly.
    Otherwise, the repositories need to be created ahead of the import.


!!! warning

    Repositories of the push type are automatically converted to sync repositories at import time.

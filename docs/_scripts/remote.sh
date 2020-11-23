#!/usr/bin/env bash
echo "Creating a remote that points to an external source of container images."
REMOTE_HREF=$(http POST $BASE_ADDR/pulp/api/v3/remotes/container/container/ \
    name='my-hello-repo' \
    url='https://registry-1.docker.io' \
    upstream_name='pulp/test-fixture-1' | jq -r '.pulp_href')

echo "Inspecting new Remote."
http $BASE_ADDR$REMOTE_HREF

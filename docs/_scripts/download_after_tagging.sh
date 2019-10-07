#!/usr/bin/env bash

export TAG_NAME='custom_tag'

export DIST_NAME='testing-tagging'
export DIST_BASE_PATH='tag'

echo "Publishing the latest repository."
export TASK_URL=$(http POST $BASE_ADDR/pulp/api/v3/distributions/container/container/ \
  name=$DIST_NAME base_path=$DIST_BASE_PATH repository=$REPO_HREF \
  | jq -r '.task')

wait_until_task_finished $BASE_ADDR$TASK_URL

export DISTRIBUTION_HREF=$(http $BASE_ADDR$TASK_URL \
  | jq -r '.created_resources | first')
export REGISTRY_PATH=$(http $BASE_ADDR$DISTRIBUTION_HREF \
  | jq -r '.registry_path')

echo "Pulling ${REGISTRY_PATH}:${TAG_NAME}."
docker run $REGISTRY_PATH:$TAG_NAME

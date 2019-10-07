#!/usr/bin/env bash

export TAG_NAME='custom_tag'

echo "Untagging a manifest which is labeled with ${TAG_NAME}"
export TASK_URL=$(http POST $BASE_ADDR'/pulp/api/v3/container/untag/' \
  repository=$REPO_HREF tag=$TAG_NAME \
  | jq -r '.task')

wait_until_task_finished $BASE_ADDR$TASK_URL

echo "Getting a reference to all removed tags."
export REPO_VERSION=$(http $BASE_ADDR$TASK_URL \
  | jq -r '.created_resources | first')
export REMOVED_TAGS=$(http $BASE_ADDR$REPO_VERSION \
  | jq -r '.content_summary | .removed | ."container.tag" | .href')

echo "List removed tags from the latest repository version."
http $BASE_ADDR$REMOVED_TAGS

#!/usr/bin/env bash

export TAG_NAME='custom_tag'
export MANIFEST_DIGEST='sha256:21e3caae28758329318c8a868a80daa37ad8851705155fc28767852c73d36af5'

echo "Tagging the manifest."
export TASK_URL=$(http POST $BASE_ADDR'/pulp/api/v3/container/tag/' \
  repository=$REPO_HREF tag=$TAG_NAME digest=$MANIFEST_DIGEST \
  | jq -r '.task')

wait_until_task_finished $BASE_ADDR$TASK_URL

echo "Getting a reference to a newly created tag."
export CREATED_TAG=$(http $BASE_ADDR$TASK_URL \
  | jq -r '.created_resources | .[] | select(test("content"))')

echo "Display properties of the created tag."
http $BASE_ADDR$CREATED_TAG

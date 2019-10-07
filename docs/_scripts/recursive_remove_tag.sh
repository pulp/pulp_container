#!/usr/bin/env bash

echo "Create a task to recursively remove the same tag to the repo."
export TASK_HREF=$(http POST $BASE_ADDR'/pulp/api/v3/container/recursive-remove/' \
  repository=$DEST_REPO_HREF \
  content_units:="[\"$TAG_HREF\"]" \
  | jq -r '.task')

# Poll the task (here we use a function defined in docs/_scripts/base.sh)
wait_until_task_finished $BASE_ADDR$TASK_HREF

# After the task is complete, it gives us a new repository version
export REMOVED_VERSION=$(http $BASE_ADDR$TASK_HREF | jq -r '.created_resources | first')

echo "Inspect RepositoryVersion."
http $BASE_ADDR$REMOVED_VERSION

#!/usr/bin/env bash

echo "Create a task to copy a tag to the repo."
export TASK_HREF=$(http POST $BASE_ADDR'/pulp/api/v3/container/tags/copy/' \
  source_repository=$REPO_HREF \
  destination_repository=$DEST_REPO_HREF \
  names:="[\"manifest_a\"]" \
  | jq -r '.task')

# Poll the task (here we use a function defined in docs/_scripts/base.sh)
wait_until_task_finished $BASE_ADDR$TASK_HREF

# After the task is complete, it gives us a new repository version
export TAG_COPY_VERSION=$(http $BASE_ADDR$TASK_HREF | jq -r '.created_resources | first')

echo "Inspect RepositoryVersion."
http $BASE_ADDR$TAG_COPY_VERSION

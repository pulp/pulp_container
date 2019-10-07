#!/usr/bin/env bash

echo "Retrieve the href of Tag manifest_a in the synced repository."
export TAG_HREF=$(http $BASE_ADDR'/pulp/api/v3/content/container/tags/?repository_version='$REPOVERSION_HREF'&name=manifest_a' \
  | jq -r '.results | first | .pulp_href')

echo "Create a task to recursively add a tag to the repo."
export TASK_HREF=$(http POST $BASE_ADDR'/pulp/api/v3/container/recursive-add/' \
  repository=$DEST_REPO_HREF \
  content_units:="[\"$TAG_HREF\"]" \
  | jq -r '.task')

# Poll the task (here we use a function defined in docs/_scripts/base.sh)
wait_until_task_finished $BASE_ADDR$TASK_HREF

# After the task is complete, it gives us a new repository version
export ADDED_VERSION=$(http $BASE_ADDR$TASK_HREF| jq -r '.created_resources | first')

echo "Inspect RepositoryVersion."
http $BASE_ADDR$ADDED_VERSION

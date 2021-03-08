#!/usr/bin/env sh

# make sure this script runs at the repo root
cd "$(dirname "$(realpath -e "$0")")"/../../..

export BASE_ADDR=http://pulp.example.com:80

cd docs/_scripts/
bash ./docs_check.sh

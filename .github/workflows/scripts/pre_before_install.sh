# make sure this script runs at the repo root
cd "$(dirname "$(realpath -e "$0")")"/../../..

set -mveuo pipefail

if [ -f "/etc/docker/daemon.json" ]
then
  echo "INFO:
  Updating docker configuration
  "

  echo "$(cat /etc/docker/daemon.json | jq -s '.[0] + {
  "insecure-registries" : ["pulp.example.com", "pulp", "pulp:80"]
  }')" | sudo tee /etc/docker/daemon.json
  sudo service docker restart || true
fi

if [ -f "/etc/containers/registries.conf" ]
then
  echo "INFO:
  Updating registries configuration
  "
  echo "[registries.insecure]
  registries = ['pulp.example.com', 'pulp', 'pulp:80']
  " | sudo tee -a /etc/containers/registries.conf
fi


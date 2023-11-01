# make sure this script runs at the repo root
cd "$(dirname "$(realpath -e "$0")")"/../../..

set -mveuo pipefail

if [ -f "/etc/docker/daemon.json" ]
then
  echo "INFO:
  Updating docker configuration
  "

  echo "$(cat /etc/docker/daemon.json | jq -s '.[0] + {
  "insecure-registries" : ["pulp.example.com", "pulp"]
  }')" | sudo tee /etc/docker/daemon.json
  sudo service docker restart || true
fi

if [ -f "/etc/containers/registries.conf" ]
then
  echo "INFO:
  Updating registries configuration
  "
  echo "[registries.insecure]
  registries = ['pulp.example.com', 'pulp']
  " | sudo tee -a /etc/containers/registries.conf
fi

# Configure the GHA host for buildah/skopeo running within the pulp container.
# Default UID & GID range is 165536-231071, which is 64K long.
# But nested buildah/skopeo always needs more than needs 64K.
# The Pulp image is configured for 64K + 10000 .
sudo sed -i "s\runner:165536:65536\runner:165536:75536\g" /etc/subuid /etc/subgid
podman system migrate


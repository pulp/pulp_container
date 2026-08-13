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
  # registries.conf v1 and v2 formats cannot be mixed in the same file;
  # detect which format the runner uses and append matching syntax.
  if grep -q "unqualified-search-registries" /etc/containers/registries.conf; then
    sudo tee -a /etc/containers/registries.conf <<'EOF'

[[registry]]
location = "pulp.example.com"
insecure = true

[[registry]]
location = "pulp"
insecure = true
EOF
  else
    sudo tee -a /etc/containers/registries.conf <<'EOF'

[registries.insecure]
registries = ["pulp.example.com", "pulp"]
EOF
  fi
fi

# Configure the GHA host for buildah/skopeo running within the pulp container.
# Default UID & GID range is 165536-231071, which is 64K long.
# But nested buildah/skopeo always needs more than needs 64K.
# The Pulp image is configured for 64K + 10000 .
sudo sed -i "s\runner:165536:65536\runner:165536:75536\g" /etc/subuid /etc/subgid
podman system migrate


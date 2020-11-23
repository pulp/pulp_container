set -mveuo pipefail


update_docker_configuration() {
  echo "INFO:
  Updating docker configuration
  "

  echo '{
  "registry-mirrors": ["https://mirror.gcr.io"],
  "insecure-registries" : ["pulp:80"],
  "mtu": 1460
}' | sudo tee /etc/docker/daemon.json
  sudo service docker restart
}


update_docker_configuration

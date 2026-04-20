SCENARIOS=("pulp" "performance" "azure" "gcp" "s3" "generate-bindings" "lowerbounds")
if [[ " ${SCENARIOS[*]} " =~ " ${TEST} " ]]; then
  # Needed by pulp_container/tests/functional/api/test_flatpak.py:
  cmd_prefix dnf install -yq dbus-daemon flatpak

  # DO NOT CALL update-ca-trust, it will break the bindings TLS
  # This copy is for the flatpak tests, flatpak uses pk11-kit which checks the source anchors
  # to build the trust chain, it doesn't actually use the output of update-ca-trust
  cmd_prefix cp /etc/pulp/certs/pulp_webserver.crt /etc/pki/ca-trust/source/anchors/pulp_webserver.crt
fi

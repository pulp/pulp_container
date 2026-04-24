SCENARIOS=("pulp" "performance" "azure" "gcp" "s3" "generate-bindings" "lowerbounds")
if [[ " ${SCENARIOS[*]} " =~ " ${TEST} " ]]; then
  # Needed by pulp_container/tests/functional/api/test_flatpak.py:
  cmd_prefix dnf install -yq dbus-daemon flatpak

  # Add the Pulp CA cert to the system trust store inside the container so that
  # flatpak/OSTree (which uses GLib/GIO) trusts the Pulp registry's TLS certificate.
  # Using cp + update-ca-trust extract (the standard RHEL9 approach) rather than
  # "trust anchor", which behaved unexpectedly when given the full CA bundle path.
  cmd_prefix bash -c "cp /etc/pulp/certs/pulp_webserver.crt /etc/pki/ca-trust/source/anchors/ && update-ca-trust extract"
fi

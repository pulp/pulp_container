SCENARIOS=("pulp" "performance" "azure" "gcp" "s3" "generate-bindings" "lowerbounds")
if [[ " ${SCENARIOS[*]} " =~ " ${TEST} " ]]; then
  # Needed by pulp_container/tests/functional/api/test_flatpak.py:
  cmd_prefix dnf install -yq dbus-daemon flatpak
fi

# add the copied certificates from install.sh to the container's trusted certificates list
if [[ "$TEST" = "azure" ]]; then
  cmd_prefix sudo trust anchor /etc/pki/tls/cert.pem
else
  cmd_prefix sudo trust anchor /etc/pulp/certs/pulp_webserver.crt
fi

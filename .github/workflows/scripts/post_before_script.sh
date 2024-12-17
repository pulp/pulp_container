# Needed by pulp_container/tests/functional/api/test_flatpak.py:
cmd_prefix dnf install -yq dbus-daemon flatpak

# add the copied certificates from install.sh to the container's trusted certificates list
if [[ "$TEST" = "azure" ]]; then
  cmd_prefix trust anchor /etc/pki/tls/cert.pem
else
  cmd_prefix trust anchor /etc/pulp/certs/pulp_webserver.crt
fi

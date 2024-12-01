# Needed by pulp_container/tests/functional/api/test_flatpak.py:
cmd_prefix dnf install -yq dbus-daemon flatpak

# add the copied certificates from install.sh to the container's trusted certificates list
cmd_prefix sudo trust anchor /etc/pulp/certs/pulp_webserver.crt

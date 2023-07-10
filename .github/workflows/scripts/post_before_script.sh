if [[ " ${SCENARIOS[*]} " =~ " ${TEST} " ]]; then
  # Needed by pulp_container/tests/functional/api/test_flatpak.py:
  cmd_prefix dnf install -yq dbus-daemon flatpak
fi

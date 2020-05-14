#!/usr/bin/env sh

echo "machine pulp
login admin
password password
" > ~/.netrc

cmd_prefix bash -c "dnf install -y openssl"
cmd_prefix bash -c "openssl ecparam -genkey -name prime256v1 -noout -out /var/lib/pulp/tmp/private.key"
cmd_prefix bash -c "openssl ec -in /var/lib/pulp/tmp/private.key -pubout -out /var/lib/pulp/tmp/public.key"

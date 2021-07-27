# make sure this script runs at the repo root
cd "$(dirname "$(realpath -e "$0")")"/../../..

set -mveuo pipefail

# add pulp.example.com  ot the /etc/hosts
# docker clients cannot identify 'pulp' as host
cat /etc/hosts | grep pulp
PULP_HOSTNAME=$(cat /etc/hosts | sed -En "s/pulp/pulp.example.com/p")
echo $PULP_HOSTNAME | sudo tee -a /etc/hosts
cat /etc/hosts | grep pulp

echo "machine pulp.example.com
login admin
password password
" >> ~/.netrc

sed -i 's/https:\/\/pulp/https:\/\/pulp.example.com/g' $PWD/.github/workflows/scripts/script.sh
sed -i 's/\"hostname\": \"pulp\",/\"hostname\": \"pulp.example.com\",/g' ~/.config/pulp_smash/settings.json

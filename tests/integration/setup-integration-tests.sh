#!/bin/bash

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# Pre-run script for integration test operator-workflows action.
# https://github.com/canonical/operator-workflows/blob/main/.github/workflows/integration_test.yaml

# The COS observability stack are deployed on K8s models.

# save original controller that is used for testing
ORIGINAL_CONTROLLER=$(juju controllers --format json | jq -r '.controllers | keys | .[0]')

echo "bootstrapping microk8s juju controller"
sudo snap install microk8s --channel=1.34-strict/stable
GROUP=snap_microk8s
sudo usermod -a -G "$GROUP" "$USER"
if [ "$(id -gn)" != "$GROUP" ]; then
  exec sg "$GROUP" "$0" "$*"
fi

if [[ "${DOCKERHUB_MIRROR}" ]]; then
  sudo tee /var/snap/microk8s/current/args/certs.d/docker.io/hosts.toml > /dev/null << EOF
server = "$DOCKERHUB_MIRROR"

[host."$DOCKERHUB_MIRROR"]
    capabilities = ["pull", "resolve"]
EOF
  cat /var/snap/microk8s/current/args/certs.d/docker.io/hosts.toml
fi

# Get preferred source IP address for metallb
IPADDR=$( { ip -4 -j route get 2.2.2.2 | jq -r '.[] | .prefsrc'; } )
sudo microk8s enable "metallb:$IPADDR-$IPADDR" "hostpath-storage"
microk8s status --wait-ready

unset JUJU_CONTROLLER
unset JUJU_MODEL
juju bootstrap microk8s microk8s
juju switch "$ORIGINAL_CONTROLLER"

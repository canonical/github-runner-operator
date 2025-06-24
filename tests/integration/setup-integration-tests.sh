#!/bin/bash

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# Pre-run script for integration test operator-workflows action.
# https://github.com/canonical/operator-workflows/blob/main/.github/workflows/integration_test.yaml

# The COS observability stack are deployed on K8s models.

# save original controller that is used for testing
ORIGINAL_CONTROLLER=$(juju controllers --format json | jq -r '.controllers | keys | .[0]')
echo "bootstrapping microk8s juju controller"
sudo snap install microk8s --channel=1.32-strict/stable
GROUP=snap_microk8s
sudo usermod -a -G $GROUP $USER
if [ $(id -gn) != $GROUP ]; then
  exec sg $GROUP "$0 $*"
fi
sudo microk8s enable hostpath-storage
microk8s status --wait-ready
juju bootstrap microk8s microk8s
unset JUJU_CONTROLLER
unset JUJU_MODEL
juju switch $ORIGINAL_CONTROLLER

#!/usr/bin/env bash

#  Copyright 2024 Canonical Ltd.
#  See LICENSE file for licensing details.

# Script to setup microstack for testing
# This script is intended to be run in a self-hosted runner, which uses proxy settings,
# and we encountered some issues with no_proxy not being interpreted correctly.

set -e

retry() {
    local command="$1"
    local wait_message="$2"
    local max_try="$3"

    local attempt=0

    while ! $command
    do
        attempt=$((attempt + 1))
        if [[ attempt -ge $max_try ]]; then
            return
        fi

        juju models || echo "Failed to list models"
        juju controllers || echo "Failed to list controllers"
        juju switch openstack || echo "Failed to switch to openstack"
        juju status --color || echo "Failed to get status"
        echo "$wait_message"
        sleep 10
    done
}
#  remove proxy vars as we encountered a problem with no_proxy not being interpreted correctly.
head -n  1 /etc/environment > temp && sudo mv temp /etc/environment
unset HTTP_PROXY HTTPS_PROXY NO_PROXY http_proxy https_proxy no_proxy
# microk8s charm installed by microstack tries to create an alias for kubectl and fails otherwise
sudo snap remove kubectl
# Install microstack
sudo snap install openstack --channel 2023.1 --devmode
sunbeam prepare-node-script | bash -x
sleep 10
# The following can take a while....
retry 'sudo -g snap_daemon sunbeam cluster bootstrap --accept-defaults' 'Waiting for cluster bootstrap to complete' 3
sudo -g snap_daemon sunbeam openrc > admin-openrc
. admin-openrc
# Test connection
openstack user list

juju clouds || echo "Failed to list clouds"
juju bootstrap localhost lxd
echo "PYTEST_ADDOPTS=--openstack-rc=${PWD}/admin-openrc" >> "${GITHUB_ENV}"

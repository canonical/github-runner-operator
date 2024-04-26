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
# microk8s charm installed by microstack tries to create an alias for kubectl and fails otherwise
sudo snap remove kubectl

# Configure and install microstack
sudo sed -i 's/microstack/microstack.multipass/g' /etc/hosts

cat <<EOF > preseed.yaml
bootstrap:
  # Management networks shared by hosts (CIDRs, separated by comma)
  management_cidr: 10.217.177.0/24
addons:
  # MetalLB address allocation range (supports multiple ranges, comma separated)
  metallb: 10.20.21.10-10.20.21.20
user:
  # Populate OpenStack cloud with demo user, default images, flavors etc
  run_demo_setup: True
  # Username to use for access to OpenStack
  username: demo
  # Password to use for access to OpenStack
  password: QNBy8XQqV3Lu
  # Network range to use for project network
  cidr: 192.168.122.0/24
  # List of nameservers guests should use for DNS resolution
  nameservers: 10.217.177.1
  # Enable ping and SSH access to instances?
  security_group_rules: True
  # Local or remote access to VMs
  remote_access_location: local
# # Local Access
# external_network:
#   # CIDR of OpenStack external network - arbitrary but must not be in use
#   cidr: 10.20.20.0/24
#   # Start of IP allocation range for external network
#   start: 10.20.20.2
#   # End of IP allocation range for external network
#   end: 10.20.20.254
#   # Network type for access to external network
#   network_type: flat
#   # VLAN ID to use for external network
#   segmentation_id:
# Remote Access
external_network:
  # CIDR of network to use for external networking
  cidr: 10.20.20.0/24
  # IP address of default gateway for external network
  gateway: 10.20.20.1
  # Start of IP allocation range for external network
  start: 10.20.20.2
  # End of IP allocation range for external network
  end: 10.20.20.254
  # Network type for access to external network
  network_type: flat
  # VLAN ID to use for external network
  segmentation_id:
  # Free network interface that will be configured for external traffic
  nic: $(ip -o -4 route show to default | awk '{print $5}')
# MicroCeph config
microceph_config:
  microstack.multipass:
    # Disks to attach to MicroCeph
    osd_devices:
EOF

sudo snap install openstack --channel 2023.1 --devmode
sudo usermod -a -G snap_daemon $USER
newgrp snap_daemon
timeout 180 sunbeam prepare-node-script | bash -x
# The following can takes around 30 mins..., set timeout 45 mins.
timeout 2700 sudo -g snap_daemon sunbeam cluster bootstrap -p preseed.yaml --accept-defaults
sudo -g snap_daemon sunbeam configure -p preseed.yaml --openrc demo-openrc --accept-defaults
# The microstack should be running now.
clouds_yaml="${PWD}/clouds.yaml"
# Use admin account for access to create flavors, etc.
sg snap_daemon -c "sunbeam cloud-config --admin" | tee "$clouds_yaml"
# Test connection
OS_CLIENT_CONFIG_FILE="$clouds_yaml" openstack --os-cloud sunbeam user show admin

juju clouds || echo "Failed to list clouds"
juju bootstrap localhost lxd
echo "PYTEST_ADDOPTS=--openstack-clouds-yaml=$clouds_yaml" >> "${GITHUB_ENV}"

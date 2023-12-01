#!/usr/bin/env bash

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

set -e

if [[ "$1" == "test" ]]; then
    /snap/bin/lxc launch ubuntu-daily:jammy builder
else
    /snap/bin/lxc launch ubuntu-daily:jammy builder --vm
fi
while ! /snap/bin/lxc exec builder -- /usr/bin/who
do
    echo "Wait for lxd agent to be ready"
    sleep 10
done
while ! /snap/bin/lxc exec builder -- /usr/bin/nslookup github.com
do
    echo "Wait for network to be ready"
    sleep 10
done

/snap/bin/lxc exec builder -- /usr/bin/apt-get update
/snap/bin/lxc exec builder --env DEBIAN_FRONTEND=noninteractive -- /usr/bin/apt-get upgrade -yq
/snap/bin/lxc exec builder --env DEBIAN_FRONTEND=noninteractive -- /usr/bin/apt-get install linux-generic-hwe-22.04 -yq

/snap/bin/lxc restart builder
while ! /snap/bin/lxc exec builder -- /usr/bin/who
do
    echo "Wait for lxd agent to be ready"
    sleep 10
done
while ! /snap/bin/lxc exec builder -- /usr/bin/nslookup github.com
do
    echo "Wait for network to be ready"
    sleep 10
done

/snap/bin/lxc exec builder -- /usr/bin/apt-get update
/snap/bin/lxc exec builder --env DEBIAN_FRONTEND=noninteractive -- /usr/bin/apt-get upgrade -yq
/snap/bin/lxc exec builder --env DEBIAN_FRONTEND=noninteractive -- /usr/bin/apt-get install docker.io npm python3-pip shellcheck jq wget yarn -yq
/snap/bin/lxc exec builder -- /usr/sbin/groupadd microk8s
/snap/bin/lxc exec builder -- /usr/sbin/usermod -aG microk8s ubuntu
/snap/bin/lxc exec builder -- /usr/sbin/usermod -aG docker ubuntu
/snap/bin/lxc exec builder -- /usr/sbin/iptables -I DOCKER-USER -j ACCEPT

# Download and verify checksum of yq
/usr/bin/wget https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64
/usr/bin/wget https://github.com/mikefarah/yq/releases/latest/download/checksums
/usr/bin/wget https://github.com/mikefarah/yq/releases/latest/download/checksums_hashes_order
/usr/bin/wget https://github.com/mikefarah/yq/releases/latest/download/extract-checksum.sh
/usr/bin/bash extract-checksum.sh SHA-256 yq_linux_amd64 | /usr/bin/awk '{print $2,$1}' | /usr/bin/sha256sum -c | /usr/bin/grep OK
/snap/bin/lxc file push yq_linux_amd64 builder/usr/bin/yq --mode 755

/snap/bin/lxc publish builder --alias builder --reuse -f

# Swap in the built image
/snap/bin/lxc image alias rename runner old-runner
/snap/bin/lxc image alias rename builder runner
/snap/bin/lxc image delete old-runner

# Clean up LXD instance
/snap/bin/lxc stop builder
/snap/bin/lxc delete builder
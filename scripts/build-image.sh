#!/usr/bin/env bash

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

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

        echo "$wait_message"
        sleep 10
    done
}

cleanup() {
    local test_command="$1"
    local clean_up_command="$2"
    local wait_message="$3"
    local max_try="$4"

    local attempt=0

    while bash -c "$test_command"
    do
        echo "$wait_message"

        $clean_up_command

        attempt=$((attempt + 1))
        if [[ attempt -ge $max_try ]]; then
            # Cleanup failure.
            return 1
        fi

        sleep 10
    done
}

HTTP_PROXY="$1"
HTTPS_PROXY="$2"
MODE="$3"

cleanup '/snap/bin/lxc info builder &> /dev/null' '/snap/bin/lxc delete builder --force' 'Cleanup LXD VM of previous run' 10

if [[ "$MODE" == "test" ]]; then
    retry '/snap/bin/lxc launch ubuntu-daily:jammy builder --device root,size=5GiB' 'Starting LXD container'
else
    retry '/snap/bin/lxc launch ubuntu-daily:jammy builder --vm --device root,size=8GiB' 'Starting LXD VM'
fi
retry '/snap/bin/lxc exec builder -- /usr/bin/who' 'Wait for lxd agent to be ready' 30
retry '/snap/bin/lxc exec builder -- /usr/bin/nslookup github.com' 'Wait for network to be ready' 30

/snap/bin/lxc exec builder -- /usr/bin/apt-get update
/snap/bin/lxc exec builder --env DEBIAN_FRONTEND=noninteractive -- /usr/bin/apt-get upgrade -yq
/snap/bin/lxc exec builder --env DEBIAN_FRONTEND=noninteractive -- /usr/bin/apt-get install linux-generic-hwe-22.04 -yq

/snap/bin/lxc restart builder
retry '/snap/bin/lxc exec builder -- /usr/bin/who' 'Wait for lxd agent to be ready' 30
retry '/snap/bin/lxc exec builder -- /usr/bin/nslookup github.com' 'Wait for network to be ready' 30

/snap/bin/lxc exec builder -- /usr/bin/apt-get update
/snap/bin/lxc exec builder --env DEBIAN_FRONTEND=noninteractive -- /usr/bin/apt-get upgrade -yq
/snap/bin/lxc exec builder --env DEBIAN_FRONTEND=noninteractive -- /usr/bin/apt-get install docker.io npm python3-pip shellcheck jq wget -yq
if [[ ! -z "$HTTP_PROXY" ]]; then
    /snap/bin/lxc npm config set proxy "$HTTP_PROXY"
fi
if [[ ! -z "$HTTPS_PROXY" ]]; then
    /snap/bin/lxc npm config set https-proxy "$HTTPS_PROXY"
fi
/snap/bin/lxc exec builder -- /usr/bin/npm install --global yarn 
/snap/bin/lxc exec builder -- /usr/sbin/groupadd microk8s
/snap/bin/lxc exec builder -- /usr/sbin/usermod -aG microk8s ubuntu
/snap/bin/lxc exec builder -- /usr/sbin/usermod -aG docker ubuntu
/snap/bin/lxc exec builder -- /usr/sbin/iptables -I DOCKER-USER -j ACCEPT

# Download and verify checksum of yq
if [[ $(uname -m) == 'aarch64' ]]; then
    YQ_ARCH="arm64"
elif [[ $(uname -m) == 'arm64' ]]; then
    YQ_ARCH="arm64"
elif [[ $(uname -m) == 'x86_64' ]]; then
    YQ_ARCH="amd64"
else
    echo "Unsupported CPU architecture: $(uname -m)"
    return 1
fi
/usr/bin/wget "https://github.com/mikefarah/yq/releases/latest/download/yq_linux_$YQ_ARCH"
/usr/bin/wget https://github.com/mikefarah/yq/releases/latest/download/checksums
/usr/bin/wget https://github.com/mikefarah/yq/releases/latest/download/checksums_hashes_order
/usr/bin/wget https://github.com/mikefarah/yq/releases/latest/download/extract-checksum.sh
/usr/bin/bash extract-checksum.sh SHA-256 "yq_linux_$YQ_ARCH" | /usr/bin/awk '{print $2,$1}' | /usr/bin/sha256sum -c | /usr/bin/grep OK
/snap/bin/lxc file push "yq_linux_$YQ_ARCH" builder/usr/bin/yq --mode 755

/snap/bin/lxc publish builder --alias builder --reuse -f

# Swap in the built image
/snap/bin/lxc image alias rename runner old-runner || true
/snap/bin/lxc image alias rename builder runner
/snap/bin/lxc image delete old-runner || true

# Clean up LXD instance
cleanup '/snap/bin/lxc info builder &> /dev/null' '/snap/bin/lxc delete builder --force' 'Cleanup LXD VM' 10

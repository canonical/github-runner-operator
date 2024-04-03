#!/usr/bin/env bash

# Copyright 2024 Canonical Ltd.
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
NO_PROXY="$3"
BASE_IMAGE="$4"
MODE="$5"

if [[ -n "$HTTP_PROXY" ]]; then
    /snap/bin/lxc config set core.proxy_http "$HTTP_PROXY"
fi
if [[ -n "$HTTPS_PROXY" ]]; then
    /snap/bin/lxc config set core.proxy_https "$HTTPS_PROXY"
fi

cleanup '/snap/bin/lxc info builder &> /dev/null' '/snap/bin/lxc delete builder --force' 'Cleanup LXD VM of previous run' 10

if [[ "$MODE" == "test" ]]; then
    retry "/snap/bin/lxc launch ubuntu-daily:$BASE_IMAGE builder --device root,size=5GiB" 'Starting LXD container'
else
    retry "/snap/bin/lxc launch ubuntu-daily:$BASE_IMAGE builder --vm --device root,size=8GiB" 'Starting LXD VM'
fi
retry '/snap/bin/lxc exec builder -- /usr/bin/who' 'Wait for lxd agent to be ready' 30
if [[ -n "$HTTP_PROXY" ]]; then
    /snap/bin/lxc exec builder -- echo "HTTP_PROXY=$HTTP_PROXY" >> /etc/environment
    /snap/bin/lxc exec builder -- echo "http_proxy=$HTTP_PROXY" >> /etc/environment
    /snap/bin/lxc exec builder -- echo "Acquire::http::Proxy \"$HTTP_PROXY\";" >> /etc/apt/apt.conf
fi
if [[ -n "$HTTPS_PROXY" ]]; then
    /snap/bin/lxc exec builder -- echo "HTTPS_PROXY=$HTTPS_PROXY" >> /etc/environment
    /snap/bin/lxc exec builder -- echo "https_proxy=$HTTPS_PROXY" >> /etc/environment
    /snap/bin/lxc exec builder -- echo "Acquire::https::Proxy \"$HTTPS_PROXY\";" >> /etc/apt/apt.conf
fi
if [[ -n "$NO_PROXY" ]]; then
    /snap/bin/lxc exec builder -- echo "NO_PROXY=$NO_PROXY" >> /etc/environment
    /snap/bin/lxc exec builder -- echo "no_proxy=$NO_PROXY" >> /etc/environment
fi
retry '/snap/bin/lxc exec builder -- /usr/bin/nslookup github.com' 'Wait for network to be ready' 30

/snap/bin/lxc exec builder -- /usr/bin/apt-get update
/snap/bin/lxc exec builder --env DEBIAN_FRONTEND=noninteractive -- /usr/bin/apt-get upgrade -yq
/snap/bin/lxc exec builder --env DEBIAN_FRONTEND=noninteractive -- /usr/bin/apt-get install linux-generic-hwe-22.04 -yq
# This will remove older version of kernel as HWE is installed now.
/snap/bin/lxc exec builder -- /usr/bin/apt-get autoremove --purge

/snap/bin/lxc restart builder
retry '/snap/bin/lxc exec builder -- /usr/bin/who' 'Wait for lxd agent to be ready' 30
retry '/snap/bin/lxc exec builder -- /usr/bin/nslookup github.com' 'Wait for network to be ready' 30

/snap/bin/lxc exec builder -- /usr/bin/apt-get update
/snap/bin/lxc exec builder --env DEBIAN_FRONTEND=noninteractive -- /usr/bin/apt-get upgrade -yq
/snap/bin/lxc exec builder --env DEBIAN_FRONTEND=noninteractive -- /usr/bin/apt-get install docker.io npm python3-pip shellcheck jq wget unzip gh -yq

# Uninstall unattended-upgrades, to avoid lock errors when unattended-upgrades is active in the runner
/snap/bin/lxc exec builder --env DEBIAN_FRONTEND=noninteractive -- /usr/bin/systemctl stop apt-daily.timer
/snap/bin/lxc exec builder --env DEBIAN_FRONTEND=noninteractive -- /usr/bin/systemctl disable apt-daily.timer
/snap/bin/lxc exec builder --env DEBIAN_FRONTEND=noninteractive -- /usr/bin/systemctl mask apt-daily.service
/snap/bin/lxc exec builder --env DEBIAN_FRONTEND=noninteractive -- /usr/bin/systemctl stop apt-daily-upgrade.timer
/snap/bin/lxc exec builder --env DEBIAN_FRONTEND=noninteractive -- /usr/bin/systemctl disable apt-daily-upgrade.timer
/snap/bin/lxc exec builder --env DEBIAN_FRONTEND=noninteractive -- /usr/bin/systemctl mask apt-daily-upgrade.service
/snap/bin/lxc exec builder --env DEBIAN_FRONTEND=noninteractive -- /usr/bin/systemctl daemon-reload
/snap/bin/lxc exec builder --env DEBIAN_FRONTEND=noninteractive -- /usr/bin/apt-get purge unattended-upgrades -yq

if [[ -n "$HTTP_PROXY" ]]; then
    /snap/bin/lxc exec builder -- /usr/bin/npm config set proxy "$HTTP_PROXY"
fi
if [[ -n "$HTTPS_PROXY" ]]; then
    /snap/bin/lxc exec builder -- /usr/bin/npm config set https-proxy "$HTTPS_PROXY"
fi
/snap/bin/lxc exec builder -- /usr/bin/npm install --global yarn 
/snap/bin/lxc exec builder -- /usr/sbin/groupadd microk8s
/snap/bin/lxc exec builder -- /usr/sbin/usermod -aG microk8s ubuntu
/snap/bin/lxc exec builder -- /usr/sbin/usermod -aG docker ubuntu
/snap/bin/lxc exec builder -- /usr/sbin/iptables -I DOCKER-USER -j ACCEPT

# Reduce image size
/snap/bin/lxc exec builder -- /usr/bin/npm cache clean --force
/snap/bin/lxc exec builder -- /usr/bin/apt-get clean

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
/usr/bin/wget "https://github.com/mikefarah/yq/releases/latest/download/yq_linux_$YQ_ARCH" -O "yq_linux_$YQ_ARCH"
/usr/bin/wget https://github.com/mikefarah/yq/releases/latest/download/checksums -O checksums
/usr/bin/wget https://github.com/mikefarah/yq/releases/latest/download/checksums_hashes_order -O checksums_hashes_order
/usr/bin/wget https://github.com/mikefarah/yq/releases/latest/download/extract-checksum.sh -O extract-checksum.sh
/usr/bin/bash extract-checksum.sh SHA-256 "yq_linux_$YQ_ARCH" | /usr/bin/awk '{print $2,$1}' | /usr/bin/sha256sum -c | /usr/bin/grep OK
/snap/bin/lxc file push "yq_linux_$YQ_ARCH" builder/usr/bin/yq --mode 755

/snap/bin/lxc exec builder -- /usr/bin/sync
/snap/bin/lxc publish builder --alias builder --reuse -f

# Swap in the built image
/snap/bin/lxc image alias rename $BASE_IMAGE old-$BASE_IMAGE || true
/snap/bin/lxc image alias rename builder $BASE_IMAGE
/snap/bin/lxc image delete old-$BASE_IMAGE || true

# Clean up LXD instance
cleanup '/snap/bin/lxc info builder &> /dev/null' '/snap/bin/lxc delete builder --force' 'Cleanup LXD instance' 10

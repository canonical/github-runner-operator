#!/usr/bin/env bash

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

set -euo pipefail

# GitHub runner bin args
RUNNER_TAR_URL="$1"

# Proxy args
HTTP_PROXY="$2"
HTTPS_PROXY="$3"
NO_PROXY="$4"
DOCKER_PROXY_SERVICE_CONF="$5"
DOCKER_PROXY_CONF="$6"

# retry function
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

# cleanup any existing mounts
cleanup() {
    sudo umount /mnt/ubuntu-image/dev/ || true
    sudo umount /mnt/ubuntu-image/proc/ || true
    sudo umount /mnt/ubuntu-image/sys/ || true
    sudo umount /mnt/ubuntu-image || true
    sudo qemu-nbd --disconnect /dev/nbd0
}

# Check if proxy variables set, doesn't exist or is a different value then update.
if [[ -n "$HTTP_PROXY" ]]; then
    if ! grep -q "HTTP_PROXY=" /etc/environment || ! grep -q "HTTP_PROXY=$HTTP_PROXY" /etc/environment; then
        sed -i "/^HTTP_PROXY=/d" /etc/environment
        echo "HTTP_PROXY=$HTTP_PROXY" >> /etc/environment
    fi
    if ! grep -q "http_proxy=" /etc/environment || ! grep -q "http_proxy=$HTTP_PROXY" /etc/environment; then
        sed -i "/^http_proxy=/d" /etc/environment
        echo "http_proxy=$HTTP_PROXY" >> /etc/environment
    fi
fi

if [[ -n "$HTTPS_PROXY" ]]; then
    if ! grep -q "HTTPS_PROXY=" /etc/environment || ! grep -q "HTTPS_PROXY=$HTTPS_PROXY" /etc/environment; then
        sed -i "/^HTTPS_PROXY=/d" /etc/environment
        echo "HTTPS_PROXY=$HTTPS_PROXY" >> /etc/environment
    fi
    if ! grep -q "https_proxy=" /etc/environment || ! grep -q "https_proxy=$HTTPS_PROXY" /etc/environment; then
        sed -i "/^https_proxy=/d" /etc/environment
        echo "https_proxy=$HTTPS_PROXY" >> /etc/environment
    fi
fi

if [[ -n "$NO_PROXY" ]]; then
    if ! grep -q "NO_PROXY=" /etc/environment || ! grep -q "NO_PROXY=$NO_PROXY" /etc/environment; then
        sed -i "/^NO_PROXY=/d" /etc/environment
        echo "NO_PROXY=$NO_PROXY" >> /etc/environment
    fi
    if ! grep -q "no_proxy=" /etc/environment || ! grep -q "no_proxy=$NO_PROXY" /etc/environment; then
        sed -i "/^no_proxy=/d" /etc/environment
        echo "no_proxy=$NO_PROXY" >> /etc/environment
    fi
fi

# Architecture args
ARCH=$(uname -m)
if [[ $ARCH == 'aarch64' ]]; then
    BIN_ARCH="arm64"
elif [[ $ARCH == 'arm64' ]]; then
    BIN_ARCH="arm64"
elif [[ $ARCH == 'x86_64' ]]; then
    BIN_ARCH="amd64"
else
    echo "Unsupported CPU architecture: $ARCH"
    return 1
fi

# qemu-utils required to unpack qcow image
sudo DEBIAN_FRONTEND=noninteractive apt-get install qemu-utils libguestfs-tools -y

# enable network block device
sudo modprobe nbd

# cleanup any existing mounts
cleanup

retry "sudo wget https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-$BIN_ARCH.img \
    -O jammy-server-cloudimg-$BIN_ARCH.img" "Downloading cloud image" 3

# resize image - installing dependencies requires more disk space
sudo qemu-img resize jammy-server-cloudimg-$BIN_ARCH.img +1.5G

# mount nbd
echo "Connecting network block device to image"
sudo qemu-nbd --connect=/dev/nbd0 jammy-server-cloudimg-$BIN_ARCH.img
sudo mkdir -p /mnt/ubuntu-image
retry "sudo mount -o rw /dev/nbd0p1 /mnt/ubuntu-image" "Mounting nbd0p1 device" 3

# mount required system dirs
echo "Mounting sys dirs"
retry "sudo mount --bind /dev/ /mnt/ubuntu-image/dev/" "Mounting /dev/" 3
retry "sudo mount --bind /proc/ /mnt/ubuntu-image/proc/" "Mounting /proc/" 3
retry "sudo mount --bind /sys/ /mnt/ubuntu-image/sys/" "Mounting /sys/" 3
sudo rm /mnt/ubuntu-image/etc/resolv.conf -f
sudo cp /etc/resolv.conf /mnt/ubuntu-image/etc/resolv.conf

# resize mount
echo "Resizing mounts"
sudo growpart /dev/nbd0 1 # grow partition size to available space
sudo resize2fs /dev/nbd0p1 # resize fs accordingly

# chroot and install dependencies
echo "Installing dependencies in chroot env"
sudo chroot /mnt/ubuntu-image/ <<EOF
set -e

# Commands within the chroot environment
df -h # print disk free space
DEBIAN_FRONTEND=noninteractive /usr/bin/apt-get update -yq
DEBIAN_FRONTEND=noninteractive /usr/bin/apt-get upgrade -yq
DEBIAN_FRONTEND=noninteractive /usr/bin/apt-get install docker.io npm python3-pip shellcheck jq wget unzip gh -yq
ln -s /usr/bin/python3 /usr/bin/python

# Uninstall unattended-upgrades, to avoid lock errors when unattended-upgrades is active in the runner
DEBIAN_FRONTEND=noninteractive /usr/bin/systemctl stop apt-daily.timer
DEBIAN_FRONTEND=noninteractive /usr/bin/systemctl disable apt-daily.timer
DEBIAN_FRONTEND=noninteractive /usr/bin/systemctl mask apt-daily.service
DEBIAN_FRONTEND=noninteractive /usr/bin/systemctl stop apt-daily-upgrade.timer
DEBIAN_FRONTEND=noninteractive /usr/bin/systemctl disable apt-daily-upgrade.timer
DEBIAN_FRONTEND=noninteractive /usr/bin/systemctl mask apt-daily-upgrade.service
DEBIAN_FRONTEND=noninteractive /usr/bin/systemctl daemon-reload
DEBIAN_FRONTEND=noninteractive /usr/bin/apt-get purge unattended-upgrades -yq

/usr/sbin/useradd -m ubuntu
/usr/bin/npm install --global yarn 
/usr/sbin/groupadd microk8s
/usr/sbin/usermod -aG microk8s ubuntu
/usr/sbin/usermod -aG docker ubuntu
/usr/bin/chmod 777 /usr/local/bin

# Proxy configs
if [[ -n "$HTTP_PROXY" ]]; then
    /usr/bin/npm config set proxy "$HTTP_PROXY"
fi
if [[ -n "$HTTPS_PROXY" ]]; then
    /usr/bin/npm config set https-proxy "$HTTPS_PROXY"
fi
if [[ -n "$DOCKER_PROXY_SERVICE_CONF" ]]; then
    mkdir -p /etc/systemd/system/docker.service.d
    echo "$DOCKER_PROXY_SERVICE_CONF" > /etc/systemd/system/docker.service.d/http-proxy.conf
fi
if [[ -n "$DOCKER_PROXY_CONF" ]]; then
    mkdir -p /root/.docker
    echo "$DOCKER_PROXY_CONF" > /root/.docker/config.json
    mkdir -p /home/ubuntu/.docker
    echo "$DOCKER_PROXY_CONF" > /home/ubuntu/.docker/config.json
fi

# Reduce image size
/usr/bin/npm cache clean --force
DEBIAN_FRONTEND=noninteractive /usr/bin/apt-get clean

# Download and verify checksum of yq
/usr/bin/wget "https://github.com/mikefarah/yq/releases/latest/download/yq_linux_$BIN_ARCH" -O "yq_linux_$BIN_ARCH"
/usr/bin/wget https://github.com/mikefarah/yq/releases/latest/download/checksums -O checksums
/usr/bin/wget https://github.com/mikefarah/yq/releases/latest/download/checksums_hashes_order -O checksums_hashes_order
/usr/bin/wget https://github.com/mikefarah/yq/releases/latest/download/extract-checksum.sh -O extract-checksum.sh
/usr/bin/bash extract-checksum.sh SHA-256 "yq_linux_$BIN_ARCH" | /usr/bin/awk '{print \$2,\$1}' | /usr/bin/sha256sum -c | /usr/bin/grep OK
rm checksums checksums_hashes_order extract-checksum.sh 
/usr/bin/chmod 755 yq_linux_$BIN_ARCH
/usr/bin/mv yq_linux_$BIN_ARCH /usr/bin/yq

# Download runner bin and verify checksum
mkdir -p /home/ubuntu/actions-runner && cd /home/ubuntu/actions-runner
/usr/bin/curl -o /home/ubuntu/actions-runner.tar.gz -L $RUNNER_TAR_URL
/usr/bin/tar xzf /home/ubuntu/actions-runner.tar.gz
rm /home/ubuntu/actions-runner.tar.gz
chown -R ubuntu /home/ubuntu/
EOF

# sync & cleanup
echo "Syncing"
sudo sync
cleanup

# Reduce image size by removing sparse space & compressing
sudo virt-sparsify --compress jammy-server-cloudimg-$BIN_ARCH.img jammy-server-cloudimg-$BIN_ARCH-compressed.img

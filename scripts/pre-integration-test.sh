#!/usr/bin/env bash

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

# Enable kernel module br_netfilter
sudo modprobe br_netfilter

# Find a loop-device
loop_device=$(sudo losetup -f)

# Install squid proxy for proxy test
default_ip="$(ip route get $(ip route show 0.0.0.0/0 | grep -oP 'via \K\S+') | grep -oP 'src \K\S+')"
sudo apt install squid
sudo sed -i 's/http_access deny/# http_access deny/g' /etc/squid/squid.conf
echo "http_access allow all" | sudo tee -a /etc/squid/squid.conf
sudo systemctl restart squid

# Output PYTEST_ADDOPTS to GitHub Actions environment
echo "PYTEST_ADDOPTS=--loop-device=$loop_device --squid-proxy=http://$default_ip:3128" >> "$GITHUB_ENV"

#!/usr/bin/env bash

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

# Enable kernel module br_netfilter
sudo modprobe br_netfilter

# Install tinyproxy
sudo apt install tinyproxy -y

# Find a loop-device
loop_device=$(sudo losetup -f)
echo "PYTEST_ADDOPTS=--loop-device=$loop_device" >> "$GITHUB_ENV"

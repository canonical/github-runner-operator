#!/usr/bin/env bash
#
#  Copyright 2026 Canonical Ltd.
#  See LICENSE file for licensing details.
#

set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

sudo apt-get install -y linux-generic-6.14

# Pin GRUB to boot the 6.14 kernel instead of the newer HWE kernel
KERNEL_ENTRY=$(sudo grep -oP "menuentry '\K[^']*6\.14[^']*" /boot/grub/grub.cfg | head -1)
sudo grub-set-default "Advanced options for Ubuntu>${KERNEL_ENTRY}"
sudo update-grub

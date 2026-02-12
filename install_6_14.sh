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
sudo sed -i 's/^GRUB_DEFAULT=.*/GRUB_DEFAULT=saved/' /etc/default/grub
sudo grub-set-default "Advanced options for Ubuntu>${KERNEL_ENTRY}"
sudo update-grub

# Prevent apt upgrade from pulling in a newer HWE kernel
sudo apt-mark hold linux-generic-hwe-24.04 linux-image-generic-hwe-24.04

# Suppress misleading "Pending Kernel Upgrade" warnings from needrestart
sudo sed -i "s/#\$nrconf{kernelhints} = -1;/\$nrconf{kernelhints} = 0;/g" /etc/needrestart/needrestart.conf

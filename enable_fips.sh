#!/usr/bin/env bash
#
#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.
#


pro attach $protoken --no-auto-enable > /dev/null 2>&1
pro enable fips-updates --assume-yes > /dev/null 2>&1
truncate -s 0 /etc/machine-id
rm /var/lib/dbus/machine-id
rm -rf /var/lib/ubuntu-advantage/private
rm -f /var/log/ubuntu-advantage*
# disable kernel checks for need restart to avoid printing "Pending Kernel Upgrade"
sudo sed -i "s/#\$nrconf{kernelhints} = -1;/\$nrconf{kernelhints} = 0;/g" /etc/needrestart/needrestart.conf

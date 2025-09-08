#!/usr/bin/env bash
#
#  Copyright 2025 Canonical Ltd.
#  See LICENSE file for licensing details.
#


pro attach $protoken --no-auto-enable
pro enable fips-updates --assume-yes
truncate -s 0 /etc/machine-id
rm /var/lib/dbus/machine-id
rm -rf /var/lib/ubuntu-advantage/private
rm -f /var/log/ubuntu-advantage*

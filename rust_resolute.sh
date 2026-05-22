#!/usr/bin/env bash
#
#  Copyright 2026 Canonical Ltd.
#  See LICENSE file for licensing details.
#

set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

sudo add-apt-repository -y ppa:dotnet/backports
sudo apt update
sudo apt-get install -yq rustup docker.io docker-buildx
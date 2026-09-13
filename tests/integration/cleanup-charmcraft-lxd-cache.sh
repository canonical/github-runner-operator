#!/bin/bash

# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

# Pre-build script for integration test operator-workflows action.
# https://github.com/canonical/operator-workflows/blob/main/.github/workflows/integration_test.yaml

# Removes stale charmcraft LXD base instances so charmcraft recreates them with
# fresh apt package lists. This avoids build failures when Ubuntu mirrors remove
# old package versions that are still referenced in cached Packages index files.

if lxc project list 2>/dev/null | grep -q "^| charmcraft"; then
    echo "Removing stale charmcraft LXD base instances..."
    lxc --project charmcraft list --format csv -c n 2>/dev/null \
        | grep "^base-instance" \
        | while IFS= read -r instance; do
            echo "Deleting $instance"
            lxc --project charmcraft delete --force "$instance" || true
        done
    echo "Cleanup complete."
else
    echo "No charmcraft LXD project found, skipping cleanup."
fi

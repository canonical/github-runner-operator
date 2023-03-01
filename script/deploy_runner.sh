#!/usr/bin/env bash

set -e

rm -f github_runner.zip

# Request a download URL for the artifact.
echo "Requesting github runner charm download link..."
DOWNLOAD_LOCATION=$(curl \
  --head \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${GITHUB_TOKEN}"\
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/repos/canonical/github-runner-operator/actions/artifacts/{$GITHUB_RUNNER_ARTIFACT_ID}/zip" \
  | grep location)
# Parse out the URL from the format "Location: URL\r".
LOCATION_ARRAY=($DOWNLOAD_LOCATION)
URL=$(echo "${LOCATION_ARRAY[1]}" | tr -d '\r')

# Download the github runner charm.
echo "Downloading github runner charm..."
curl -o github_runner.zip "$URL"

# Decompress the zip.
echo "Decompressing github runner charm..."
unzip -p github_runner.zip > github-runner.charm
rm github_runner.zip

# Deploy the charm.
juju deploy ./github-runner.charm --series=jammy e2e-runner
juju config e2e-runner token="$GITHUB_TOKEN" path=canonical/github-runner-operator virtual-machines=1

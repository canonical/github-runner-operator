#!/bin/bash
# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

curl -o openapi.yaml https://git.launchpad.net/job-manager/plain/openapi/openapi.yaml?h=main
docker run --rm -v "${PWD}:/local" openapitools/openapi-generator-cli generate -i /local/openapi.yaml  --package-name jobmanager_client -g python-pydantic-v1 -o /local/client
sudo chown -R "$USER" ./client

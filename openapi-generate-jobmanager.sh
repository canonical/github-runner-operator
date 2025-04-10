#!/bin/bash

docker run --rm -v ${PWD}:/local openapitools/openapi-generator-cli generate -i /local/openapi.yaml  --package-name jobmanager_client -g python-pydantic-v1 -o /local/jobmanager/client
sudo chown -R "$USER" ./jobmanager

#!/usr/bin/env bash

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

juju remove-application e2e-runner --force --destroy-storage --no-wait

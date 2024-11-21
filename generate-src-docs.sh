#!/usr/bin/env bash

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

lazydocs --no-watermark --output-path src-docs src/*.py
lazydocs --no-watermark --output-path github-runner-manager/src-docs github-runner-manager/src/*

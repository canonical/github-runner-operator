# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

terraform {
  required_providers {
    juju = {
      source  = "juju/juju"
      version = ">= 0.11.0, < 1.0.0"
    }
  }
  required_version = ">= 1.0.0"
}

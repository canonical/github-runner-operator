# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

terraform {
  required_providers {
    juju = {
      source  = "juju/juju"
      version = ">= 1.0.0"
    }
  }
}

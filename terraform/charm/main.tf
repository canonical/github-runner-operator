# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

resource "juju_application" "github_runner" {
  name  = var.app_name
  model = var.model

  charm {
    name     = "github-runner"
    channel  = var.channel
    revision = var.revision
    base     = var.base
  }

  config      = var.config
  constraints = var.constraints
  units       = var.units
}

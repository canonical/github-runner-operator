# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

terraform {
  required_version = ">= 1.6.6"
  required_providers {
    juju = {
      source  = "juju/juju"
      version = "< 2.0.0"
    }
  }
}

provider "juju" {}

resource "juju_model" "test_model" {
  name = "test-model"
}

# Provision a machine and reuse its ID in module placements
resource "juju_machine" "m0" {
  model = juju_model.test_model.name
  base  = "ubuntu@22.04"
  name  = "machine_0"
}

# Scenario: two applications deployed on a single machine
module "runner_a" {
  source      = "./.."
  app_name    = "github-runner-a"
  model       = juju_model.test_model.name
  channel     = "latest/edge"
  revision    = null
  base        = "ubuntu@22.04"
  units       = 1
  machines    = [juju_machine.m0.machine_id]
  config      = {}
  constraints = ""
}

module "runner_b" {
  source      = "./.."
  app_name    = "github-runner-b"
  model       = juju_model.test_model.name
  channel     = "latest/edge"
  revision    = null
  base        = "ubuntu@22.04"
  units       = 1
  machines    = [juju_machine.m0.machine_id]
  config      = {}
  constraints = ""
}

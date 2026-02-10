# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

terraform {
  required_version = ">= 1.6.6"
  required_providers {
    juju = {
      source  = "juju/juju"
      version = ">= 1.0, < 2.0"
    }
  }
}

provider "juju" {}

resource "juju_model" "test_model" {
  name  = "test-model"
  owner = "admin"
}

# Provision a machine and reuse its ID in module placements
resource "juju_machine" "m0" {
  model_uuid = juju_model.test_model.uuid
  base       = "ubuntu@22.04"
  name       = "machine_0"
}

# Scenario: two applications deployed on a single machine
module "runner_a" {
  source      = "./.."
  app_name    = "github-runner-a"
  model_uuid  = juju_model.test_model.uuid
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
  model_uuid  = juju_model.test_model.uuid
  channel     = "latest/edge"
  revision    = null
  base        = "ubuntu@22.04"
  units       = 1
  machines    = [juju_machine.m0.machine_id]
  config      = {}
  constraints = ""
}

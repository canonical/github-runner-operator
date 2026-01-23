terraform {
  required_version = ">= 1.6.6"
  required_providers {
    juju = {
      source  = "juju/juju"
      version = ">= 0.11.0"
    }
  }
}

provider "juju" {}

# Provision a machine and reuse its ID in module placements
resource "juju_machine" "machine_0" {
  model = "test-model"
  base  = "ubuntu@22.04"
  name  = "machine_0"
}

# Scenario: two applications deployed on a single machine
module "runner_a" {
  source      = "./.."
  app_name    = "github-runner-a"
  model       = "test-model"
  channel     = "latest/stable"
  revision    = null
  base        = "ubuntu@22.04"
  units       = 1
  machines    = [juju_machine.machine_0.machine_id]
  config      = {}
  constraints = ""
}

module "runner_b" {
  source      = "./.."
  app_name    = "github-runner-b"
  model       = "test-model"
  channel     = "latest/stable"
  revision    = null
  base        = "ubuntu@22.04"
  units       = 1
  machines    = [juju_machine.machine_0.machine_id]
  config      = {}
  constraints = ""
}

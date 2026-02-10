# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

run "two_apps_one_machine" {
  module {
    source = "./."
  }
  command = apply

  # runner_a assertions
  assert {
    condition     = module.runner_a.app_name == "github-runner-a"
    error_message = "runner_a name should match"
  }

  assert {
    condition     = module.runner_a.model == juju_model.test_model.uuid
    error_message = "runner_a model UUID should pass through"
  }

  assert {
    condition     = module.runner_a.machines == toset([juju_machine.m0.machine_id])
    error_message = "runner_a should be placed on the created machine"
  }

  assert {
    condition     = module.runner_a.units == 1
    error_message = "units should be equal to number of machines are provided (runner_a)"
  }

  # runner_b assertions
  assert {
    condition     = module.runner_b.app_name == "github-runner-b"
    error_message = "runner_b name should match"
  }

  assert {
    condition     = module.runner_b.model == juju_model.test_model.uuid
    error_message = "runner_b model UUID should pass through"
  }

  assert {
    condition     = module.runner_b.machines == toset([juju_machine.m0.machine_id])
    error_message = "runner_b should be placed on the created machine"
  }

  assert {
    condition     = module.runner_b.units == 1
    error_message = "units should be equal to number of machines are provided (runner_b)"
  }
}

run "two_apps_one_machine" {
  command = plan

  # runner_a assertions
  assert {
    condition     = module.runner_a.juju_application.github_runner.name == "github-runner-a"
    error_message = "runner_a name should match"
  }

  assert {
    condition     = module.runner_a.juju_application.github_runner.model == "test-model"
    error_message = "runner_a model should pass through"
  }

  assert {
    condition     = module.runner_a.juju_application.github_runner.machines == toset([juju_machine.m0.machine_id])
    error_message = "runner_a should be placed on the created machine"
  }

  assert {
    condition     = module.runner_a.juju_application.github_runner.units == null
    error_message = "units should be null when machines are provided (runner_a)"
  }

  # runner_b assertions
  assert {
    condition     = module.runner_b.juju_application.github_runner.name == "github-runner-b"
    error_message = "runner_b name should match"
  }

  assert {
    condition     = module.runner_b.juju_application.github_runner.model == "test-model"
    error_message = "runner_b model should pass through"
  }

  assert {
    condition     = module.runner_b.juju_application.github_runner.machines == toset([juju_machine.m0.machine_id])
    error_message = "runner_b should be placed on the created machine"
  }

  assert {
    condition     = module.runner_b.juju_application.github_runner.units == null
    error_message = "units should be null when machines are provided (runner_b)"
  }
}

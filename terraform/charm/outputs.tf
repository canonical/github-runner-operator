# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

output "app_name" {
  description = "Name of the deployed application."
  value       = juju_application.github_runner.name
}

output "model_uuid" {
  description = "Model UUID the application is deployed to."
  value       = juju_application.github_runner.model_uuid
}

output "machines" {
  description = "Set of machine IDs the application is placed on (if any)."
  value       = juju_application.github_runner.machines
}

output "units" {
  description = "Number of units to deploy when machines are not provided."
  value       = juju_application.github_runner.units
}

output "requires" {
  value = {
    debug_ssh              = "debug-ssh"
    github_runner_image_v0 = "image"
    mongodb_client         = "mongodb"
  }
}

output "provides" {
  value = {
    cos_agent = "cos-agent"
    github_runner_planner_v0 = "planner"
  }
}

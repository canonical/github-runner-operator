# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

output "github_runner_image_builder_app_name" {
  description = "Name of the the deployed github-runner-image-builder application."
  value       = module.github_runner_image_builder.app_name
}

output "reactive_runners_names" {
  description = "Names of the all the deployed github-runner applications that are reactive."
  value       = [for github_runner in var.github_runners : github_runner.app_name if lookup(github_runner.config, "max-total-virtual-machines", 0) > 0]
}

output "all_runners_names" {
  description = "Names of the all the deployed github-runner applications."
  value       = [for github_runner in values(module.github_runner) : github_runner.app_name]
}

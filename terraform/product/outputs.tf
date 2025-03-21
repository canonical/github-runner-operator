# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

output "github_runner_image_builder_app_name" {
  description = "Name of the the deployed github-runner-image-builder application."
  value       = module.github_runner_image_builder.app_name
}

output "reactive_runners_names" {
  description = "Names of the all the deployed github-runner applications that are reactive."
  value       = [for gh_runner in var.github_runners : gh_runner.app_name if lookup(gh_runner.config, "max-total-virtual-machines", 0) > 0]
}

output "all_runners_names" {
  description = "Names of the all the deployed github-runner applications."
  value       = [for gh_runner in values(module.github_runner) : gh_runner.app_name]
}

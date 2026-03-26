# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

output "github_runner_image_builder_app_name" {
  description = "Name of the the deployed github-runner-image-builder application."
  value       = module.github_runner_image_builder.app_name
}

output "all_runner_names" {
  description = "Names of the all the deployed github-runner applications."
  value       = [for github_runner in values(module.github_runner) : github_runner.app_name]
}


output "all_app_names" {
  description = "Names of the all the deployed apps, github-runner plus github-runner-image-builder."
  value       = concat([for github_runner in values(module.github_runner) : github_runner.app_name], [module.github_runner_image_builder.app_name])
}

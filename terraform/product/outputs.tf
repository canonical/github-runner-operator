# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

output "github_runner_image_builder_app_name" {
  description = "Name of the the deployed github-runner-image-builder application."
  value       = module.github_runner_image_builder.app_name
}

output "reactive_runner_names" {
  description = "Names of the all the deployed github-runner applications that are reactive."
  value       = [for github_runner in var.github_runners : github_runner.app_name if lookup(github_runner.config, "max-total-virtual-machines", 0) > 0]
}

output "all_runner_names" {
  description = "Names of the all the deployed github-runner applications."
  value       = [for github_runner in values(module.github_runner) : github_runner.app_name]
}


output "all_app_names" {
  description = "Names of the all the deployed apps, github-runner plus github-runner-image-builder."
  value       = concat([for github_runner in values(module.github_runner) : github_runner.app_name], [module.github_runner_image_builder.app_name])
}


output "planner_offers" {
  description = "Juju offers for each GitHub runner"
  value = {
    for name, offer in juju_offer.planner :
    name => {
      url  = offer.url
      name = offer.name
    }
  }
}
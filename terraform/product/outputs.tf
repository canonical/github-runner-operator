output "github_runner_image_builder_app_name" {
  description = "TODO"
  value       = module.github_runner_image_builder.app_name
}

output "reactive_runners_names" {
  description = "TODO"
  # value       = keys(module.github_runner)
  # value       = [for v in values(module.github_runner): v.app_name]
  # value       = [for v in var.github_runners: v.app_name if v.config.max-total-virtual-machines > 0]
  value = [for gh in var.github_runners : gh.app_name if lookup(gh.config, "max-total-virtual-machines", 0) > 0]
}

output "all_runners_names" {
  description = "TODO"
  # value       = keys(module.github_runner)
  value = [for v in values(module.github_runner) : v.app_name]
  # value       = [for v in var.github_runners: v.app_name if v.config.max-total-virtual-machines > 0]
  # value = [for gh in var.github_runners: gh.app_name if lookup(gh.config, "max-total-virtual-machines", 0) > 0]
}

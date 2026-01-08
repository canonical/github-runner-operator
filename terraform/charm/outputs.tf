# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

output "app_name" {
  description = "Name of the deployed application."
  value       = juju_application.github_runner.name
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
  }
}

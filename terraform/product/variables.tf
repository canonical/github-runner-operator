# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

variable "model" {
  description = "Reference to the Juju model to deploy the github-runner and github-runner-image-builder operators."
  type        = string
}

variable "github_runner_image_builder" {
  type = object({
    app_name    = optional(string, "github-runner-image-builder")
    channel     = optional(string, "latest/stable")
    config      = optional(map(string), {})
    constraints = optional(string, "arch=amd64 cores=2 mem=8192M root-disk=20000M")
    revision    = optional(number)
    base        = optional(string, "ubuntu@22.04")
    units       = optional(number, 1)
  })
}

variable "github_runners" {
  type = list(object({
    app_name    = optional(string, "github-runner")
    channel     = optional(string, "latest/stable")
    config      = optional(map(string), {})
    constraints = optional(string, "arch=amd64 cores=2 mem=8192M root-disk=20000M")
    revision    = optional(number)
    base        = optional(string, "ubuntu@22.04")
    units       = optional(number, 1)
  }))

  validation {
    condition     = length(var.github_runners) > 0
    error_message = "At least one github-runner should be defined"
  }
  validation {
    condition     = length(var.github_runners) == length(toset([for github_runner in var.github_runners : github_runner.app_name]))
    error_message = "Each github-runner app_name must be unique."
  }

}

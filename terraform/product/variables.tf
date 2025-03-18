# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

variable "model" {
  description = "Reference to the Juju model to deploy the github-runner operator."
  type        = string
}

variable "github_runner_image_builder_model" {
  description = "Reference to the Juju model to deploy the github-runner-image-builder operator."
  type        = string
}

variable "github_runner" {
  type = object({
    app_name    = optional(string, "github-runner")
    channel     = optional(string, "latest/edge")
    config      = optional(map(string), {})
    constraints = optional(string, "arch=amd64")
    revision    = optional(number)
    base        = optional(string, "ubuntu@22.04")
    units       = optional(number, 1)
  })
}

variable "github_runner_image_builder" {
  type = object({
    app_name    = optional(string, "github-runner-image-builder")
    channel     = optional(string, "latest/edge")
    config      = optional(map(string), {})
    constraints = optional(string, "arch=amd64")
    revision    = optional(number)
    base        = optional(string, "ubuntu@22.04")
    units       = optional(number, 1)
  })
}

variable "github_runners" {
  type = list(object({
    app_name    = optional(string, "github-runner")
    channel     = optional(string, "latest/edge")
    config      = optional(map(string), {})
    constraints = optional(string, "arch=amd64")
    revision    = optional(number)
    base        = optional(string, "ubuntu@22.04")
    units       = optional(number, 1)
  }))

  validation {
    condition     = length(var.github_runners) > 0
    error_message = "At least one github-runner should be defined"
  }
  validation {
    condition     = length(var.github_runners) == length(toset([for runner in var.github_runners : runner.app_name]))
    error_message = "Each github-runner app_name must be unique."
  }

}

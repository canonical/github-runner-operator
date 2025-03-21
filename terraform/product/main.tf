# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

data "juju_model" "github_runner" {
  name = var.model
}

module "github_runner" {
  for_each = { for gh in var.github_runners : gh.app_name => gh }

  source      = "../charm"
  app_name    = each.key
  channel     = each.value.channel
  config      = each.value.config
  constraints = each.value.constraints
  model       = data.juju_model.github_runner.name
  revision    = each.value.revision
  base        = each.value.base
  units       = each.value.units
}

module "github_runner_image_builder" {
  source      = "git::https://github.com/canonical/github-runner-image-builder-operator//terraform/charm?ref=rev67"
  app_name    = var.github_runner_image_builder.app_name
  channel     = var.github_runner_image_builder.channel
  config      = var.github_runner_image_builder.config
  constraints = var.github_runner_image_builder.constraints
  model       = data.juju_model.github_runner.name
  revision    = var.github_runner_image_builder.revision
  base        = var.github_runner_image_builder.base
  units       = var.github_runner_image_builder.units
}

resource "juju_integration" "image_builder" {
  model = data.juju_model.github_runner.name

  for_each = { for github_runner in module.github_runner : github_runner.app_name => github_runner }

  application {
    name     = each.key
    endpoint = each.value.requires.github_runner_image_v0
  }

  application {
    name     = module.github_runner_image_builder.app_name
    endpoint = module.github_runner_image_builder.provides.github_runner_image_v0
  }
}

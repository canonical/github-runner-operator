# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

resource "juju_application" "tmate" {
  name  = "tmate-ssh-server"
  model = local.juju_model_name
  units = 1

  charm {
    name     = "tmate-ssh-server"
    revision = 10
    channel  = "latest/edge"
    base     = "ubuntu@22.04"
  }

  expose {}
}



resource "juju_integration" "tmate_ssh" {
  model = local.juju_model_name

  for_each = toset(module.github_runner.all_runners_names)

  application {
    name     = each.key
    endpoint = "debug-ssh"
  }

  application {
    name     = juju_application.tmate.name
    endpoint = "debug-ssh"
  }
}


terraform {
  required_version = ">= 1.6.6"
  required_providers {
    juju = {
      source  = "juju/juju"
      version = ">= 0.10.1"
    }
  }
}

locals {
  grafana_agent_amd_revision = 164
  grafana_agent_arm_revision = 166
}


resource "juju_application" "grafana_agent" {
  name  = var.grafana_agent_name
  model = var.juju_model_name
  units = 0

  charm {
    name     = "grafana-agent"
    revision = var.is_grafana_agent_on_arm ? local.grafana_agent_arm_revision : local.grafana_agent_amd_revision
    channel  = "latest/edge"
    base     = var.grafana_agent_charm_base
  }
}

resource "juju_integration" "grafana_agent" {
  model = var.juju_model_name

  for_each = toset(var.applications_to_relate)

  application {
    name     = each.key
    endpoint = "cos-agent"
  }

  application {
    name     = juju_application.grafana_agent.name
    endpoint = "cos-agent"
  }
}


resource "juju_integration" "grafana_dashboard" {
  model = var.juju_model_name
  count = var.grafana_dashboard_offer_url != "" ? 1 : 0

  application {
    name     = juju_application.grafana_agent.name
    endpoint = "grafana-dashboards-provider"
  }

  application {
    offer_url = var.grafana_dashboard_offer_url
  }
}


resource "juju_integration" "loki_logging" {
  model = var.juju_model_name
  count = var.loki_logging_offer_url != "" ? 1 : 0

  application {
    name     = juju_application.grafana_agent.name
    endpoint = "logging-consumer"
  }

  application {
    offer_url = var.loki_logging_offer_url
  }
}


resource "juju_integration" "prometheus_write" {
  model = var.juju_model_name
  count = var.prometheus_write_offer_url != "" ? 1 : 0

  application {
    name     = juju_application.grafana_agent.name
    endpoint = "send-remote-write"
  }

  application {
    offer_url = var.prometheus_write_offer_url
  }
}

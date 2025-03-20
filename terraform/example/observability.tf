# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# Avoid race conditions with duplicate dashboards and
# log pollution on grafana in case of duplicate dashboards
# by using a separate grafana-agent charm for the edge flavor to transmit the dashboard.

locals {
  grafana_dashboard_offer_url = "sunbeam-controller:openstack.delapuente.es/observability.grafana-dashboards"
  prometheus_write_offer_url  = "sunbeam-controller:openstack.delapuente.es/observability.prometheus-receive-remote-write"
  loki_logging_offer_url      = "sunbeam-controller:openstack.delapuente.es/observability.loki-logging"
}

module "cos_integration_with_dashboard" {
  source                      = "./modules/cos"
  juju_model_name             = local.juju_model_name
  grafana_agent_name          = "grafana-agent-with-dashboard"
  grafana_dashboard_offer_url = local.grafana_dashboard_offer_url
  loki_logging_offer_url      = local.loki_logging_offer_url
  prometheus_write_offer_url  = local.prometheus_write_offer_url
  applications_to_relate      = [module.github_runner.all_runners_names[0]]
}

module "cos_integration_without_dashboard" {
  source                     = "./modules/cos"
  juju_model_name            = local.juju_model_name
  grafana_agent_name         = "grafana-agent-without-dashboard"
  loki_logging_offer_url     = local.loki_logging_offer_url
  prometheus_write_offer_url = local.prometheus_write_offer_url
  applications_to_relate     = slice(module.github_runner.all_runners_names, 1, length(module.github_runner.all_runners_names))
}


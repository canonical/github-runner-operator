# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

variable "juju_model_name" {
  description = "Juju model name"
  type        = string
}

variable "grafana_agent_charm_base" {
  description = "Charm base for grafana agent"
  type        = string
  default     = "ubuntu@22.04"
}

variable "grafana_agent_name" {
  description = "Grafana agent application name"
  type        = string
}

variable "is_grafana_agent_on_arm" {
  description = "Boolean indicating whether the ARM64 architecture should be used for the Grafana agent. Otherwise AMD64 is used."
  type        = bool
  default     = false
}


variable "grafana_dashboard_offer_url" {
  description = "URL to the grafana dashboard offer. If not specified, the dashboard will not be related."
  type        = string
  default     = ""
}

variable "loki_logging_offer_url" {
  description = "URL to the loki logging offer. If not specified, loki will not be related."
  type        = string
  default     = ""
}

variable "prometheus_write_offer_url" {
  description = "URL to the prometheus write offer. If not specified, prometheus will not be related."
  type        = string
  default     = ""
}

variable "applications_to_relate" {
  type        = list(any)
  description = "List of application names to integrate with COS"
}

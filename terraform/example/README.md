# Some commands

Delete everything (without `terraform plan -destroy`)
```
rm -rf terraform.tfstate terraform.tfstate.backup .terraform .terraform.lock.hcl; juju destroy-model stg-ps6-github-runner --no-prompt; juju add-model stg-ps6-github-runner localhost
```

Start
```
terraform init && terraform apply -var-file=./secrets.tfvars
```

Observability CMR
```
juju consume sunbeam-controller:openstack.delapuente.es/observability.grafana-dashboards
juju integrate grafana-agent-with-dashboard grafana-dashboards
terraform import -var-file=secrets.tfvars "module.cos_integration_with_dashboard.juju_integration.grafana_dashboard[0]" "stg-ps6-github-runner:grafana-agent-with-dashboard:grafana-dashboards-provider:grafana-dashboards:grafana-dashboard"

juju consume sunbeam-controller:openstack.delapuente.es/observability.loki-logging
juju integrate grafana-agent-with-dashboard loki-logging
terraform import -var-file=secrets.tfvars "module.cos_integration_with_dashboard.juju_integration.loki_logging[0]" "stg-ps6-github-runner:loki-logging:logging:grafana-agent-with-dashboard:logging-consumer"
juju integrate grafana-agent-without-dashboard loki-logging
terraform import -var-file=secrets.tfvars "module.cos_integration_without_dashboard.juju_integration.loki_logging[0]" "stg-ps6-github-runner:loki-logging:logging:grafana-agent-without-dashboard:logging-consumer"

juju consume sunbeam-controller:openstack.delapuente.es/observability.prometheus-receive-remote-write
juju integrate grafana-agent-with-dashboard prometheus-receive-remote-write
terraform import -var-file=secrets.tfvars "module.cos_integration_with_dashboard.juju_integration.prometheus_write[0]" "stg-ps6-github-runner:prometheus-receive-remote-write:receive-remote-write:grafana-agent-with-dashboard:send-remote-write"
juju integrate grafana-agent-without-dashboard prometheus-receive-remote-write
terraform import -var-file=secrets.tfvars "module.cos_integration_without_dashboard.juju_integration.prometheus_write[0]" "stg-ps6-github-runner:prometheus-receive-remote-write:receive-remote-write:grafana-agent-without-dashboard:send-remote-write"
```

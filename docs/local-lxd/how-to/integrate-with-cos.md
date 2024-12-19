# How to integrate with COS

This guide demonstrates the process of integrating with the [Canonical Observability Stack (COS)](https://charmhub.io/topics/canonical-observability-stack) using the optional `cos-agent` integration provided by this charm.

The `cos-agent` integration can be consumed by the [grafana-agent](https://charmhub.io/grafana-agent) charm, which is responsible for transmitting logs, Prometheus metrics, and Grafana dashboards to the COS stack.

> NOTE: The Github Runner charm and `grafana-agent` charm function as machine charms, while the COS stack comprises Kubernetes charms. Therefore, establishing [cross-model integrations](https://juju.is/docs/juju/manage-cross-model-integrations) is necessary, along with potential firewall rule configurations to allow inter-model traffic.


## Requirements 
1. Deploy the Github Runner Charm with the application name `github-runner` in the `machine-model`.
2. Deploy the COS stack on a Kubernetes cloud (refer to [this tutorial](https://charmhub.io/topics/canonical-observability-stack/tutorials/install-microk8s)).
   - Ensure `loki`, `prometheus`, `grafana`, and `traefik` charms are deployed within a model named `k8s-model`.
   - Integration between `loki` and `traefik` is required to enable `grafana-agent` to transmit logs by setting a public IP for the Loki service accessible from the machine cloud.
   - Confirm that both models exist in the same Juju controller. If not, adjust the model names by appending the respective controller name (followed by ":") in the subsequent steps. Ensure you have the necessary [permissions](https://juju.is/docs/juju/manage-cross-model-integrations#heading--control-access-to-an-offer) to consume the offers.

## Steps

1. Deploy the `grafana-agent` charm in the machine model.
   ```shell
   juju switch machine-model
   juju deploy grafana-agent --channel latest/edge
   ```
2. Integrate the `grafana-agent` charm with the Github Runner charm.
   ```shell
   juju integrate github-runner grafana-agent
   ```
3. Create offers for `loki`, `prometheus`, and `grafana-agent` in the `k8s-model`.
   ```shell
   juju switch k8s-model
   juju offer loki:logging
   juju offer prometheus:receive-remote-write
   juju offer grafana:grafana-dashboard
   ```
4. Consume the offers in the machine model.
   ```shell
   juju switch machine-model
   juju consume loki
   juju consume prometheus
   juju consume grafana
   ```
5. Integrate the `grafana-agent` charm with `loki`, `prometheus`, and `grafana`.
   ```shell
   juju integrate loki-k8s grafana-agent
   juju integrate prometheus-k8s grafana-agent
   juju integrate grafana-k8s grafana-agent
   ```

You should now be able to access a Grafana Dashboard named `GitHub Self-Hosted Runner Metrics`, displaying metrics, and another named `System Resources` exhibiting host resources in Grafana.
Additionally, you can explore Loki logs using Grafana's Explore function. For detailed information about the specific metrics in the `GitHub Self-Hosted Runner Metrics` dashboard, refer to [Metrics](https://charmhub.io/github-runner/docs/reference-cos).

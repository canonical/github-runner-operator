[![CharmHub Badge](https://charmhub.io/github-runner/badge.svg)](https://charmhub.io/github-runner)
[![Promote charm](https://github.com/canonical/github-runner-operator/actions/workflows/promote_charm.yaml/badge.svg)](https://github.com/canonical/github-runner-operator/actions/workflows/promote_charm.yaml)
[![Discourse Status](https://img.shields.io/discourse/status?server=https%3A%2F%2Fdiscourse.charmhub.io&style=flat&label=CharmHub%20Discourse)](https://discourse.charmhub.io)

# GitHub runner

## Description

This machine charm creates [self-hosted runners for running GitHub Actions](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners). Each unit of this charm will start a configurable number of LXD based containers and virtual
machines to host them. Every runner performs only one job, after which it unregisters from GitHub to ensure that each job runs in
a clean environment.

The charm will periodically check the number of runners and spawn or destroy runners as necessary to match the number provided by configuration of
runners. Both the reconciliation interval and the number of runners to maintain are configurable.

## Usage

Please refer to the tutorial in `docs/tutorial/quick-start.md`.

## COS
The charm is designed to provide comprehensive metrics and monitoring capabilities for both the Runners and the Charm itself. These metrics are made available through the `cos-agent` integration with the `cos_agent` interface. Additionally, a Grafana Dashboard is included to help visualize these metrics effectively.

### Loki Integration
#### Loki Push API
The charm integrates seamlessly with Loki, a powerful log aggregation system, through the `cos-agent` integration. This integration allows the charm to push various metrics and logs related to the runners and the charm itself to a Loki instance. This provides valuable insight into the performance and behaviour of your deployment.

### Grafana Dashboard
To make monitoring even more accessible, the charm comes with a pre-configured Grafana dashboard. This dashboard is designed to visualise the metrics collected by the charm, making it easier for operators to track the health and performance of the system.
This dashboard can be transferred to Grafana using the [Grafana Agent](https://charmhub.io/grafana-agent), which consumes the `cos-agent` integration.

## Development

This charm uses black and flake8 for formatting. Both run with the lint stage of tox.

## Testing

Testing is run via tox and pytest. The unit test can be ran with `tox -e unit` and the integration test on juju 3.1 with `tox -e integration-juju3.1`.

Dependencies are installed in virtual environments. Integration testing requires a juju controller to execute. These tests will use the existing controller, creating an ephemeral model for the tests which is removed after testing. If you do not already have a controller setup, you can configure a local instance via LXD, see the [upstream documentation](https://juju.is/docs/lxd-cloud) for details.

## Generating src docs for every commit

Run the following command:

```bash
echo -e "tox -e src-docs\ngit add src-docs\n" >> .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

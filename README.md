[![CharmHub Badge](https://charmhub.io/github-runner-operator/badge.svg)](https://charmhub.io/github-runner-operator)
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

There are two mandatory configuration options - `path` and `token`.

* `path` determines the organization or repository that the runner will be registered with;
* `token` is a [GitHub Personal Access Token (PAT)](https://github.com/settings/tokens) (note: this is not the same as the token given in the Add a Runner instructions). The PAT token requires either:
  * the **`repo`** ("Full control of private repositories") permission for
use with repositories or;
  * both the **`repo`** and **`admin:org`** ("Full control of orgs and teams, read and write org projects") permissions for use with an organization. This is necessary because the charm will create and remove runners as needed to ensure that each runner executes only one job to protect jobs from leaking information to other jobs running on the same runner.

The number of runners on a single unit is configured using two configuration options that can be both used at the same time:

* the `containers` option configures the number of LXD container runners;
* the `virtual-machines` option configures the number of LXD virtual machine runners.

For example, if the charm is deployed with 2 units `juju deploy <charm> -n 2` and the `containers` value of 3 is in use,
there will be a total of 6 container based runners, three on each unit.

## Reconciliation

Each unit will periodically check the number of runners at the interval specified by `check-interval` to maintain the appropriate number. During the check, all the offline runners are unregistered from GitHub.

If there are more idle runners than configured, the oldest idle runners are unregistered and destroyed. If there are less idle runners than configured, new runners are spawned and registered with GitHub.

During each time period, every unit will make one or more API calls to GitHub. The interval may need to be adjusted if the number of units is large enough to trigger [Rate Limiting](https://docs.github.com/en/rest/overview/resources-in-the-rest-api#rate-limiting).


## COS
The charm is designed to provide comprehensive metrics and monitoring capabilities for both the Runners and the Charm itself. These metrics are made available through the `metrics-logging` integration with the `loki_push_api` interface. Additionally, a Grafana Dashboard is included to help visualize these metrics effectively.

### Loki Integration
#### Loki Push API
The charm seamlessly integrates with Loki, a powerful log aggregation system, through the `loki_push_api` interface. This integration allows the charm to push various metrics and logs related to the Runners and the Charm itself to a Loki instance. This provides valuable insights into the performance and behavior of your deployment.

### Grafana Dashboard
To make monitoring even more accessible, the charm comes with a pre-configured Grafana Dashboard. This dashboard is designed to visualize the metrics collected by the charm, making it easier for operators to track the health and performance of the system.

#### Automated Dashboard Deployment
You can automate the deployment of the Grafana Dashboard using the [cos-integration-k8s](https://charmhub.io/cos-configuration-k8s) charm. This simplifies the setup process and ensures that your monitoring infrastructure is ready to go with minimal manual intervention.

#### Configuration Options
To enable the automated deployment of the Grafana Dashboard, you can provide the following configuration options when deploying the `cos-integration-k8s` charm:

```ini
git_repo=https://https://github.com/canonical/github-runner-operator
git_branch=main
git_depth=1
grafana_dashboards_path=src/grafana_dashboard_metrics
```





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

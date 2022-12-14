# GitHub runner

## Description

This machine charm creates self-hosted GitHub runners. Each unit of this charm will start a configurable number of LXD based containers and virtual
machines to host them. Each runner performs only one job, after which it unregisters from GitHub to ensure that each job runs in
a clean environment.

The charm will periodically check the number of idle runners and spawn or destroy runners as necessary to match the number provided by configuration of
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

Each unit will periodically check the number of idle runners at the interval specified by `check-interval` to maintain the appropriate number. During the check, all the offline runners are unregistered from GitHub and corresponding containers or virtual machines are destroyed.

If there are more idle runners than configured, the oldest idle runners are unregistered and destroyed. If there are less idle runners than configured, new runners are spawn and registered with GitHub.

This means that each interval, each unit will make one or more API calls to GitHub. The interval may need to be adjusted if the number of units is large enough to trigger [Rate Limiting](https://docs.github.com/en/rest/overview/resources-in-the-rest-api#rate-limiting).

## Development

This charm uses black and flake8 for formatting. Both run with the lint stage of tox.


## Testing

Testing is run via tox and pytest. To run the full test run:

    tox

Dependencies are installed in virtual environments. Integration testing requires a juju controller to execute. These tests will use the existing controller, creating an ephemeral model for the tests which is removed after the testing. If you do not already have a controller setup, you can configure a local instance via LXD, see the [upstream documentation][https://juju.is/docs/lxd-cloud] for details.
# GitHub runner

## Description

This charm creates self hosted GitHub runners. Each unit of this charm will create start a configurable number of runners in LXD containers. Each runner performs only one job
after which the LXD is destroyed preventing the job from interacting with any other jobs. The charm will periodically check the number of currently active runners and spawn a new
runner as necessary. Both the interval of the check and the number of runners to maintain are configurable.

## Usage

There are two mandatory configuration options, `path` and `token`. Path is used to determine the organization or repository that the runner will be registered to. This value can
not be changed, the charm should be redeployed with a new value instead. The token is a [GitHub Personal Access Token (PAT)](https://github.com/settings/tokens) (note: this is not the same as the token given in the Add a Runner instructions). This token requires **`repo`** ("Full control of private repositories") for
use with repositories and both **`repo`** and **`admin:org`** ("Full control of orgs and teams, read and write org projects") for use with an organization. This is necessary because the charm will be creating and removing runners in order to
make runners single use which protects jobs from leaking information to other jobs run on the same runner.

With these values set the number of runners is controlled by the number of units you deploy and the number of runners on each unit. The config setting `quantity` configures how
many runners a single unit has and each unit is the same. For example, if this charm is deployed with 2 units `juju deploy <charm> -n 2` and the default `quantity` of 3 is in use
there will be a total of 6 runners registered, three on each of the two units. Decreasing the `quantity` config will not shut down runners, but will not spawn new ones until the
number of runners on the unit is below the new value.

Finally the interval that units check the quantity of runners is configured in cron syntax with the `check-interval` setting. Each unit will check the quantity of runners on this
interval. Runners take some time to spawn and the default time checks relatively frequently to start replacing runners. During the check, any offline runners are also removed from
the configured organization or repository. This means that each interval, each unit will make one or more API calls. The interval may need to be lengthened if the number of units
is large enough to trigger [Rate Limiting](https://docs.github.com/en/rest/overview/resources-in-the-rest-api#rate-limiting).

## Development

This charm uses black and flake8 for formatting. Both are run with the lint stage of tox.


## Testing

Testing is run via tox and pytest. To run the full test run:

    tox

Dependencies are installed in virtual environments. Integration testing requires a juju controller to execute. These tests will use the existing controller, creating an ephemeral
model for the tests which is removed after the testing. If you do not already have a controller setup, you can configure a local instance via LXD, see the [upstream
documentation][https://juju.is/docs/lxd-cloud] for details.

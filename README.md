# GitHub runner
[![CharmHub Badge](https://charmhub.io/github-runner/badge.svg)](https://charmhub.io/github-runner)
[![Promote charm](https://github.com/canonical/github-runner-operator/actions/workflows/promote_charm.yaml/badge.svg)](https://github.com/canonical/github-runner-operator/actions/workflows/promote_charm.yaml)
[![Discourse Status](https://img.shields.io/discourse/status?server=https%3A%2F%2Fdiscourse.charmhub.io&style=flat&label=CharmHub%20Discourse)](https://discourse.charmhub.io)

This machine charm creates self-hosted runners for running GitHub Actions. Each unit of this charm will start a configurable number of OpenStack or LXD based virtual machines to host them. Every runner performs only one job, after which it unregisters from GitHub to ensure that each job runs in a clean environment.

To host local LXD based virtual machines, you have to use the track `local-lxd`. See [juju channels](https://discourse.charmhub.io/t/channel/6562) for more information on channels.

The charm will periodically check the number of runners and spawn or destroy runners as necessary to match the number provided by configuration of runners. Both the reconciliation interval and the number of runners to maintain are configurable.

Like any Juju charm, this charm supports one-line deployment, configuration, integration, scaling, and more. For GitHub runner, this includes:
* Scaling the number of runners up or down
* Configuration for the resources of virtual machines
* Configuration for the reconciliation interval to check/adjust the number of runners
* [COS integration](https://charmhub.io/topics/canonical-identity-platform/how-to/integrate-cos)

For information about how to deploy, integrate, and manage this charm, see the official [GitHub Runner Documentation](https://charmhub.io/github-runner).

## Get started

In order to get familiar with the charm, it is recommended to follow the [GitHub Runner tutorial](https://charmhub.io/github-runner/docs/tutorial-quick-start) which will guide you through the process of deploying the charm
and executing a workflow job using GitHub actions.

For more information about a production deployment, the how-to-guide
[How to spawn OpenStack runner](https://charmhub.io/github-runner/docs/how-to-openstack-runner) can be useful.

### Basic operations
A usual deployment of the charm can be done with the following command (please replace items in `<>` with your own values):

```bash
juju deploy github-runner --channel=latest/stable --config openstack-clouds-yaml="$(cat clouds.yaml)" --config openstack-flavor=<flavor> --config openstack-network=<openstack-network> --config path=<org>/<repo> --config token=<github-token>
```

with a cloud configuration (for the OpenStack tenant used to spawn runner VM's) in `clouds.yaml`:

```yaml
clouds:
  <cloud-name>:
    auth:
      auth_url: <keystone-auth-url>
      project_name: <project>
      username: <username>
      password: <password>
      user_domain_name: <user-domain-name>
      project_domain_name: <project-domain-name>
    region_name: <region>
  ```

Assuming you have already deployed the [Github Runner Image Builder](https://charmhub.io/github-runner-image-builder) charm
with the name `github-runner-image-builder`, you can use the following command to integrate it with the GitHub Runner charm:

```bash
juju integrate github-runner-image-builder github-runner
```

You can scale the amount of virtual machines using

```bash
juju config github-runner virtual-machines=5
```

You can change the reconciliation interval, to e.g. 5 minutes, using

```bash
juju config github-runner reconciliation-interval=5
```

You can trigger reconciliation manually using an action (assuming the unit is named `github-runner/0`):

```bash
juju run github-runner/0 reconcile-runners
```

If you need to flush and replace the runners with a new set of runners, you can use the following command:

```bash
juju run github-runner/0 flush-runners
```


## Integrations
The charm supports [multiple integrations](https://charmhub.io/github-runner/integrations),
but in order to deploy the charm using OpenStack VM's for the runners, you need it to relate it
with an image-builder using the [image](https://charmhub.io/github-runner/integrations#image) 
endpoint. Via this integration, the charm detects the supported images to use for spawning the virtual machines.


## Repository structure

This repository contains the charm in the root directory and the Python package `github-runner-manager` in the
`github-runner-manager` directory. Refer to [Contributing](CONTRIBUTING.md) for more information.


## Learn more
* [Read more](https://charmhub.io/github-runner)
* [Developer documentation](https://charmhub.io/github-runner/docs/how-to-contribute)

## Project and community
* [Issues](https://github.com/canonical/github-runner-operator/issues)
* [Contributing](https://charmhub.io/github-runner/docs/how-to-contribute)
* [Matrix](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)

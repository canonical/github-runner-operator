# Contributing

## Overview

This document explains the processes and practices recommended for contributing enhancements to the GitHub runner operator.

- Generally, before developing enhancements to this charm, you should consider [opening an issue
  ](https://github.com/canonical/github-runner-operator/issues) explaining your use case.
- If you would like to chat with us about your use-cases or proposed implementation, you can reach
  us at [Canonical Mattermost public channel](https://chat.charmhub.io/charmhub/channels/charm-dev)
  or [Discourse](https://discourse.charmhub.io/).
- Familiarising yourself with the [Charmed Operator Framework](https://juju.is/docs/sdk) library
  will help you a lot when working on new features or bug fixes.
- All enhancements require review before being merged. Code review typically examines
  - code quality
  - test coverage
  - user experience for Juju operators of this charm.
- Please help us out in ensuring easy to review branches by rebasing your pull request branch onto the `main` branch. This also avoids merge commits and creates a linear Git commit history.

## Developing

The code for this charm can be downloaded as follows:

```
git clone https://github.com/canonical/github-runner-operator.git
```

You can use the environments created by `tox` for development:

```shell
tox --notest -e unit
source .tox/unit/bin/activate
```

### Testing

The following commands can then be used to run the tests:

* `tox`: Runs all of the basic checks (`lint`, `unit`, `static`, and `coverage-report`).
* `tox -e fmt`: Runs formatting using `black` and `isort`.
* `tox -e lint`: Runs a range of static code analysis to check the code.
* `tox -e static`: Runs other checks such as `bandit` for security issues, and `mypy` for type checking.
* `tox -e unit`: Runs the unit tests.
* `tox -e integration`: Runs the integration tests.

## Build charm

Build the charm in this git repository using:

```shell
charmcraft pack
```

### Deploy

```shell
# Create a model
juju add-model runner-dev
# Enable DEBUG logging
juju model-config logging-config="<root>=INFO;unit=DEBUG"
# Configure the machine resource created by the model
juju set-model-constraints mem=8G cores=2 root-disk=50G
# Deploy the charm (Assuming you're on amd64)
juju deploy ./github-runner_ubuntu-22.04-amd64_ubuntu-20.04-amd64.charm
```

## Canonical Contributor Agreement

Canonical welcomes contributions to the Indico Operator. Please check out our [contributor agreement](https://ubuntu.com/legal/contributors) if you're interested in contributing to the solution.
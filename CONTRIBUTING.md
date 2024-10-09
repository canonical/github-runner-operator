# Contribute

## Overview

This document explains the processes and practices recommended for contributing enhancements to the GitHub Runner operator.

* Generally, before developing enhancements to this charm, you should consider [opening an issue](https://github.com/canonical/github-runner-operator/issues) explaining your use case.
* If you would like to chat with us about your use-cases or proposed implementation, you can reach us at [Canonical Mattermost public channel](https://chat.charmhub.io/charmhub/channels/charm-dev) or [Discourse](https://discourse.charmhub.io/).
* Familiarizing yourself with the [Charmed Operator Framework](https://juju.is/docs/sdk) library will help you a lot when working on new features or bug fixes.
* All enhancements require review before being merged. Code review typically examines
  * code quality
  * test coverage
  * user experience for Juju administrators of this charm.
For more details, check our [contributing guide](https://github.com/canonical/is-charms-contributing-guide/blob/main/CONTRIBUTING.md).

## Developing

For any problems with this charm, please [report bugs here](https://github.com/canonical/github-runner-operator/issues).

The code for this charm can be downloaded as follows:

```shell
git clone https://github.com/canonical/github-runner-operator.git
```

Prior to working on the charm ensure juju is connected to an LXD cloud,  see the [upstream documentation](https://juju.is/docs/lxd-cloud) for details.

### Testing

This project uses `tox` for managing test environments. There are some pre-configured environments
that can be used for linting and formatting code when you're preparing contributions to the charm:

* `tox`: Runs all of the basic checks (`lint`, `unit`, `static`, and `coverage-report`).
* `tox -e fmt`: Runs formatting using `black` and `isort`.
* `tox -e lint`: Runs a range of static code analysis to check the code.
* `tox -e static`: Runs other checks such as `bandit` for security issues.
* `tox -e unit`: Runs the unit tests.
* `tox -e integration`: Runs the integration tests.

### Generating src docs for every commit

Run the following command:

```bash
echo -e "tox -e src-docs\ngit add src-docs\n" >> .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

### Building the charm

Build the charm in this git repository using:

```shell
charmcraft pack
```

## Canonical Contributor Agreement

Canonical welcomes contributions to the GitHub Runner Operator. Please check out our [contributor agreement](https://ubuntu.com/legal/contributors) if you’re interested in contributing to the solution.

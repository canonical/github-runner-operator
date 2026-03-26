# Contributing

This document explains the processes and practices recommended for contributing enhancements to the GitHub runner Operator.

## Overview

- Generally, before developing enhancements to this charm, you should consider [opening an issue
  ](https://github.com/canonical/github-runner-operator/issues) explaining your use case.
- If you would like to chat with us about your use-cases or proposed implementation, you can reach
  us at [Canonical Matrix public channel](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)
  or [Discourse](https://discourse.charmhub.io/).
- Familiarizing yourself with the [Juju documentation](https://documentation.ubuntu.com/juju/3.6/howto/manage-charms/)
  will help you a lot when working on new features or bug fixes.
- All enhancements require review before being merged. Code review typically examines
  - code quality
  - test coverage
  - user experience for Juju operators of this charm.
- Once your pull request is approved, we squash and merge your pull request branch onto
  the `main` branch. This creates a linear Git commit history.
- For further information on contributing, please refer to our
  [Contributing Guide](https://github.com/canonical/is-charms-contributing-guide).

## Code of conduct

When contributing, you must abide by the
[Ubuntu Code of Conduct](https://ubuntu.com/community/ethos/code-of-conduct).

## Changelog

Please ensure that any new feature, fix, or significant change is documented by
adding an entry to the [CHANGELOG.md](docs/changelog.md) file. Use the date of the
contribution as the header for new entries.

To learn more about changelog best practices, visit [Keep a Changelog](https://keepachangelog.com/).

## Submissions

If you want to address an issue or a bug in this project,
notify in advance the people involved to avoid confusion;
also, reference the issue or bug number when you submit the changes.

- [Fork](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/working-with-forks/about-forks)
  our [GitHub repository](https://github.com/canonical/github-runner-operator)
  and add the changes to your fork, properly structuring your commits,
  providing detailed commit messages and signing your commits.
- Make sure the updated project builds and runs without warnings or errors;
  this includes linting, documentation, code and tests.
- Submit the changes as a
  [pull request (PR)](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request-from-a-fork).

Your changes will be reviewed in due time; if approved, they will be eventually merged.

### AI

You are free to use any tools you want while preparing your contribution, including
AI, provided that you do so lawfully and ethically.

Avoid using AI to complete issues tagged with the "good first issues" label. The
purpose of these issues is to provide newcomers with opportunities to contribute
to our projects and gain coding skills. Using AI to complete these tasks
undermines their purpose.

We have created instructions and tools that you can provide AI while preparing your contribution: [`copilot-collections`](https://github.com/canonical/copilot-collections)

While it isn't necessary to use `copilot-collections` while preparing your
contribution, these files contain details about our quality standards and
practices that will help the AI avoid common pitfalls when interacting with
our projects. By using these tools, you can avoid longer review times and nitpicks.

If you choose to use AI, please disclose this information to us by indicating
AI usage in the PR description (for instance, marking the checklist item about
AI usage). You don't need to go into explicit details about how and where you used AI.

Avoid submitting contributions that you don't fully understand.
You are responsible for the entire contribution, including the AI-assisted portions.
You must be willing to engage in discussion and respond to any questions, comments,
or suggestions we may have. 

### Signing commits

To improve contribution tracking,
we use the [Canonical contributor license agreement](https://assets.ubuntu.com/v1/ff2478d1-Canonical-HA-CLA-ANY-I_v1.2.pdf)
(CLA) as a legal sign-off, and we require all commits to have verified signatures.

#### Canonical contributor agreement

Canonical welcomes contributions to the GitHub runner Operator. Please check out our
[contributor agreement](https://ubuntu.com/legal/contributors) if you're interested in contributing to the solution.

The CLA sign-off is simple line at the
end of the commit message certifying that you wrote it
or have the right to commit it as an open-source contribution.

#### Verified signatures on commits

All commits in a pull request must have cryptographic (verified) signatures.
To add signatures on your commits, follow the
[GitHub documentation](https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits).

## Develop

To make contributions to this charm, you'll need a working
[development setup](https://documentation.ubuntu.com/juju/latest/howto/manage-your-juju-deployment/set-up-your-juju-deployment-local-testing-and-development/).

The code for this charm can be downloaded as follows:

```
git clone https://github.com/canonical/github-runner-operator
```

Make sure to install [`uv`](https://docs.astral.sh/uv/). For example, you can install `uv` on Ubuntu using:

```bash
sudo snap install astral-uv --classic
```

For other systems, follow the [`uv` installation guide](https://docs.astral.sh/uv/getting-started/installation/).

Then install `tox` with its extensions, and install a range of Python versions:

```bash
uv python install
uv tool install tox --with tox-uv
uv tool update-shell
```

To create a development environment, run:

```bash
uv sync --all-groups
source .venv/bin/activate
```

### Test

This project uses `tox` for managing test environments. There are some pre-configured environments
that can be used for linting and formatting code when you're preparing contributions to the charm:

* ``tox``: Executes all of the basic checks and tests (``lint``, ``unit``, ``static``, and ``coverage-report``).
* ``tox -e fmt``: Runs formatting using ``ruff``.
* ``tox -e lint``: Runs a range of static code analysis to check the code.
* ``tox -e static``: Runs other checks such as ``bandit`` for security issues.
* ``tox -e unit``: Runs the unit tests.
* ``tox -e integration``: Runs the integration tests.

### Build the rock and charm

Use [Rockcraft](https://documentation.ubuntu.com/rockcraft/stable/) to create an
OCI image for the GitHub runner app, and then upload the image to a MicroK8s registry,
which stores OCI archives so they can be downloaded and deployed.

Enable the MicroK8s registry:

```bash
microk8s enable registry
```

The following commands pack the OCI image and push it into
the MicroK8s registry:

```bash
cd <project_dir>
rockcraft pack
skopeo --insecure-policy copy --dest-tls-verify=false oci-archive:<rock-name>.rock docker://localhost:32000/<app-name>:latest
```

Build the charm in this git repository using:

```shell
charmcraft pack
```

### Deploy

```bash
# Create a model
juju add-model charm-dev
# Enable DEBUG logging
juju model-config logging-config="<root>=INFO;unit=DEBUG"
# Deploy the charm
juju deploy ./github-runner*.charm 
```




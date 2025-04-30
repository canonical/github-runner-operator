# GitHub Runner Operator

A [Juju](https://juju.is/) [charm](https://juju.is/docs/olm/charmed-operators) for deploying and managing [GitHub self-hosted runners](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners) on virtual machines. The charm maintains a set of self-hosted runners, each isolated in a single-use virtual machine instance. 

Like any Juju charm, this charm supports one-line deployment, configuration, integration, scaling, and more. 
For the github-runner-operator charm, this includes:
* Stateless operation.
* Configurable resource limits.
* Ability to redeploy without losing any data (no need to back up).
* Supported observability through the `cos-agent` integration.
* Scheduled dependences upgrades to mitigate security risks. Furthermore, the landscape-client charm can be deployed with this charm to ensure other dependencies are kept up to date.

Operating a self-hosted runner comes with [certain security concerns according to GitHub](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners#self-hosted-runner-security).
Just like GitHub's runners, the self-hosted runners managed by the charm are isolated in a single-use virtual machine.

Metrics and logs about the runners and the charm itself are collected and sent to the [Canonical Observability Stack](https://charmhub.io/topics/canonical-observability-stack) for analysis and visualisation.

The charm enforces a set of GitHub repository settings as best practice. This is planned to be opt-in in the future. See [How to comply with security requirements](https://charmhub.io/github-runner/docs/how-to-comply-security).

## In this documentation

| | |
|--|--|
|  [Overview](https://charmhub.io/github-runner)</br>  Overview of the charm </br> | [How-to guides](https://charmhub.io/github-runner/docs/how-to-openstack-runner) </br> Step-by-step guides covering key operations and common tasks |
| [Reference](https://charmhub.io/github-runner/docs/reference-actions) </br> Technical information - specifications, APIs, architecture | [Explanation](https://charmhub.io/github-runner/docs/explanation-charm-architecture) </br> Concepts - discussion and clarification of key topics  |

If you want to use ephemeral LXD virtual machines spawned by charm, you can refer to the section [Track local-lxd](https://charmhub.io/github-runner/docs/local-lxd).

## Contributing to this documentation

Documentation is an important part of this project, and we take the same open-source approach to the documentation as the code. As such, we welcome community contributions, suggestions and constructive feedback on our documentation. Our documentation is hosted on the [Charmhub forum](https://discourse.charmhub.io/t/github-runner-documentation-overview/7817) to enable easy collaboration. Please use the "Help us improve this documentation" links on each documentation page to either directly change something you see that's wrong, ask a question, or make a suggestion about a potential change via the comments section.

If there's a particular area of documentation that you'd like to see that's missing, please [file a bug](https://github.com/canonical/github-runner-operator/issues).

## Project and community

The GitHub runner charm is a member of the Ubuntu family. It's an open-source project that warmly welcomes community projects, contributions, suggestions, fixes, and constructive feedback.

- [Code of conduct](https://ubuntu.com/community/code-of-conduct)
- [Get support](https://discourse.charmhub.io/)
- [Join our online chat](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)
- [Contribute](Contribute)

Thinking about using the GitHub runner charm for your next project? [Get in touch](https://matrix.to/#/#charmhub-charmdev:ubuntu.com)!

# Contents

1. [How to](how-to)
  1. [Change repository or organization](how-to/change-path.md)
  1. [Change GitHub personal access token](how-to/change-token.md)
  1. [Add custom labels](how-to/add-custom-labels.md)
  1. [Debug with SSH](how-to/debug-with-ssh.md)
  1. [Integrate with COS](how-to/integrate-with-cos.md)
  1. [Spawn OpenStack runner](how-to/openstack-runner.md)
  1. [Set up reactive spawning](how-to/reactive.md)
  1. [Comply with security requirements](how-to/comply-security.md)
  1. [Contribute](how-to/contribute.md)
1. [Reference](reference)
  1. [Actions](reference/actions.md)
  1. [Configurations](reference/configurations.md)
  1. [COS Integration](reference/cos.md)
  1. [GitHub runner cryptographic overview](reference/cryptographic-overview.md)
  1. [External Access](reference/external-access.md)
  1. [Integrations](reference/integrations.md)
  1. [Token scopes](reference/token-scopes.md)
1. [Explanation](explanation)
  1. [Charm architecture](explanation/charm-architecture.md)
  1. [SSH Debug](explanation/ssh-debug.md)
1. [Changelog](changelog.md)
1. [Track local-lxd](local-lxd)
  1. [Tutorial](local-lxd/tutorial)
    1. [Managing resource usage](local-lxd/tutorial/managing-resource-usage.md)
    1. [Quick start](local-lxd/tutorial/quick-start.md)
  1. [How to](local-lxd/how-to)
    1. [Add custom labels](local-lxd/how-to/add-custom-labels.md)
    1. [Change repository or organization](local-lxd/how-to/change-path.md)
    1. [Change GitHub personal access token](local-lxd/how-to/change-token.md)
    1. [Comply with security requirements](local-lxd/how-to/comply-security.md)
    1. [Configure runner storage](local-lxd/how-to/configure-runner-storage.md)
    1. [Debug with SSH](local-lxd/how-to/debug-with-ssh.md)
    1. [Deploy on ARM64](local-lxd/how-to/deploy-on-arm64.md)
    1. [Integrate with COS](local-lxd/how-to/integrate-with-cos.md)
    1. [Comply with repository policies](local-lxd/how-to/repo-policy.md)
    1. [Run on LXD cloud](local-lxd/how-to/run-on-lxd.md)
    1. [Set base image](local-lxd/how-to/set-base-image.md)
  1. [Reference](local-lxd/reference)
    1. [Actions](local-lxd/reference/actions.md)
    1. [ARM64](local-lxd/reference/arm64.md)
    1. [Configurations](local-lxd/reference/configurations.md)
    1. [COS Integration](local-lxd/reference/cos.md)
    1. [GitHub runner cryptographic overview](local-lxd/reference/cryptographic-overview.md)
    1. [External Access](local-lxd/reference/external-access.md)
    1. [Integrations](local-lxd/reference/integrations.md)
    1. [Token scopes](local-lxd/reference/token-scopes.md)
  1. [Explanation](local-lxd/explanation)
    1. [ARM64](local-lxd/explanation/arm64.md)
    1. [Charm architecture](local-lxd/explanation/charm-architecture.md)
    1. [SSH Debug](local-lxd/explanation/ssh-debug.md)
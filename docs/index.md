A [Juju](https://juju.is/) [charm](https://juju.is/docs/olm/charmed-operators) for deploying and managing [GitHub self-hosted runners](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners) on virtual machines.

This charm simplifies initial deployment and "day N" operations of GitHub self-hosted runners. The charm makes it easy to manage self-hosted runners with security and hardware resource usage in mind.

Operating a self-hosted runner comes with [certain security concerns according to GitHub](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners#self-hosted-runner-security).
Just like GitHub's, the self-hosted runners managed by the charm are isolated in a single-use virtual machine. However, arbitrary code execution is possible under certain repository settings. This can be leveraged by malicious actors in a number of ways, such as, crypto-mining. To combat this, the charm enforces a set of GitHub repository settings to ensure the executed code is reviewed by someone trusted.

The charm also upgrades dependencies on a schedule to mitigate security risks. The upgrade includes linux kernel upgrades, automatically rebooting the machines. This ensures the latest security patches are installed within minutes.

The charm maintains a set of ephemeral self-hosted runners, each isolated in a single-use virtual machine instance. To prevent disk IO exhaustion, random access memory is used as disk for the virtual machine instances. In addition, resource limits for the self-hosted runners can be configured.

This charm will make operating GitHub self-hosted runners simple and straightforward for DevOps or SRE teams through Juju's clean interface.

## In this documentation

| | |
|--|--|
|  [Tutorials](https://charmhub.io/github-runner/docs/quick-start)</br>  Get started - a hands-on introduction to using the GitHub runner charm for new users </br> | [How-to guides](https://charmhub.io/github-runner/docs/how-to-comply-security) </br> Step-by-step guides covering key operations and common tasks |
| [Reference](https://charmhub.io/github-runner/docs/actions) </br> Technical information - specifications, APIs, architecture | [Explanation](https://charmhub.io/github-runner/docs/charm-architecture) </br> Concepts - discussion and clarification of key topics  |

## Contributing to this documentation

Documentation is an important part of this project, and we take the same open-source approach to the documentation as the code. As such, we welcome community contributions, suggestions and constructive feedback on our documentation. Our documentation is hosted on the [Charmhub forum](https://discourse.charmhub.io/t/github-runner-documentation-overview/7817) to enable easy collaboration. Please use the "Help us improve this documentation" links on each documentation page to either directly change something you see that's wrong, ask a question, or make a suggestion about a potential change via the comments section.

If there's a particular area of documentation that you'd like to see that's missing, please [file a bug](https://github.com/canonical/github-runner-operator/issues).

## Project and community

The GitHub runner charm is a member of the Ubuntu family. It's an open-source project that warmly welcomes community projects, contributions, suggestions, fixes, and constructive feedback.

- [Code of conduct](https://ubuntu.com/community/code-of-conduct)
- [Get support](https://discourse.charmhub.io/)
- [Join our online chat](https://chat.charmhub.io/charmhub/channels/charm-dev)
- [Contribute](Contribute)

Thinking about using the GitHub runner charm for your next project? [Get in touch](https://chat.charmhub.io/charmhub/channels/charm-dev)!

# Contents

1. [Tutorial](tutorial)
  1. [Quick start](tutorial/quick-start.md)
  1. [Managing resource usage](tutorial/managing-resource-usage.md)
1. [How to](how-to)
  1. [How to run on LXD cloud](how-to/run-on-lxd.md)
  1. [How to comply with security requirements](how-to/comply-security.md)
  1. [How to change GitHub personal access token](how-to/change-token.md)
  1. [How to change repository or organization](how-to/change-path.md)
  1. [How to contribute](how-to/contribute.md)
1. [Reference](reference)
  1. [Actions](reference/actions.md)
  1. [Configurations](reference/configurations.md)
1. [Explanation](explanation)
  1. [Charm architecture](explanation/charm-architecture.md)
A [Juju](https://juju.is/) [charm](https://juju.is/docs/olm/charmed-operators) deploying and managing [GitHub self-hosted runners](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners) on virtual machines.

This charm simplifies initial deployment and "day N" operations of GitHub self-hosted runners. The charm requires a [GitHub personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) and a GitHub repository or organization to connect to. The charm makes it easy to managed self-hosted runners with security and hardware resource usage in mind.

The charm maintains a set of ephemeral self-hosted runner each isolated in a virtual machine instance. The resource usage of the self-hosted runners can be configured.

This charm will make operating GitHub self-hosted runners simple and straightforwared for DevOps or SRE teams through Juju's clean interface.

## In this documentation

| | |
|--|--|
| [Tutorials](https://charmhub.io/github-runner/docs/tutorial)</br> Get started - a hands-on introduction to using the GitHub runner charm for new users </br> | [How-to guides]() </br> Step-by-step guides covering key operations and common tasks |
| [Reference]() </br> Technical information - specifications, APIs, architecture | [Explanation]() </br> Concepts - discussion and clarification of key topics |

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

# Github-runner operator
A [Juju](https://juju.is/) [charm](https://juju.is/docs/olm/charmed-operators) deploying self-hosted GitHub runners.
  
Each unit of this charm will start a configurable number of LXD based containers and virtual machines to host them. Each runner performs only one
job, after which it unregisters from GitHub to ensure that each job runs in a clean environment. The charm will periodically check the number of idle runners and spawn or destroy them as
necessary to maintain the configured number of runners. Both the reconciliation interval and the number of runners to maintain are configurable.

## Contributing to this documentation
Documentation is an important part of this project, and we take the same open-source approach to the documentation as the code. As such, we welcome community contributions, suggestions and constructive feedback on our documentation. Our documentation is hosted on the [Charmhub forum](https://discourse.charmhub.io/t/github-runner-documentation-overview/7817) to enable easy collaboration. Please use the "Help us improve this documentation" links on each documentation page to either directly change something you see that's wrong, ask a question, or make a suggestion about a potential change via the comments section.

If there's a particular area of documentation that you'd like to see that's missing, please [file a bug](https://github.com/canonical/github-runner-operator/issues).

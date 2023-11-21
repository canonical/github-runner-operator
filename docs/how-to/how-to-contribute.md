# How to change repository or organization

This charm supports changing the GitHub repository or GitHub organization the self-hosted runners are connected to.

By using [`juju config`](https://juju.is/docs/juju/juju-config) to change the [charm configuration path](https://charmhub.io/github-runner/configure#path) to another repository or organization, the charm should unregistry and remove the old self-hosted runners and create new ones connected to the new configuration.

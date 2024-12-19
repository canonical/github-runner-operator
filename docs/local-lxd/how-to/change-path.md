# How to change repository or organisation

This charm supports changing the GitHub repository or GitHub organisation the self-hosted runners are connected to.

By using [`juju config`](https://juju.is/docs/juju/juju-config) to change the [charm configuration path](https://charmhub.io/github-runner/configure#path) to another repository or organisation, the charm unregisters and removes the old self-hosted runners and instantiates new ones for the new configuration.

```shell
juju config <APP_NAME> path=<PATH>
```

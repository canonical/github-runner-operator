# How to change GitHub personal access token

This charm supports changing the [GitHub personal access token (PAT)](https://github.com/settings/tokens) used.

## Fine grained access token scopes

### Organizational Runners

The following are the permissions scopes required for the GitHub runners when registering as an
organisational runner.

Organisation:

- Self-hosted runners: read & write

Repository:

- Administration: read
- Contents: read
- Pull requests: read

### Repository Runners

- Contents: read
- Metadata: read
- Pull requests: read


## Personal access token scope

To use this charm for GitHub repositories, the following scopes should be selected:

- `repo`

To use this charm for GitHub organisations, the following scopes should be selected:

- `repo`
- `admin:org`

## Changing the token

By using [`juju config`](https://juju.is/docs/juju/juju-config) to change the [charm configuration token](https://charmhub.io/github-runner/configure#token) the charm unregisters and removes the old self-hosted runners and instantiates new ones.

```shell
juju config <APP_NAME> token=<TOKEN>
```
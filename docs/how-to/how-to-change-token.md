# How to change GitHub personal access token

This charm supports changing [GitHub personal access token (PAT)](https://github.com/settings/tokens) used. As the token will expire upon a pre-determined time when created, the token needs to be change from time to time.

## Personal access token scope

For using this charm with GitHub repository the following scopes should be selected:

- `repo`

For using this charm with GitHub organization the following scopes should be selected:

- `repo`
- `admin:org`

## Changing the token

By using [`juju config`](https://juju.is/docs/juju/juju-config) to change the [charm configuration token](https://charmhub.io/github-runner/configure#token) the charm should unregistry and remove the old self-hosted runners and create new ones.

# How to change GitHub personal access token

This charm supports changing the [GitHub personal access token (PAT)](https://github.com/settings/tokens) used.

## Changing the token

Create a new [GitHub Personal Access Token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens).

An example classic token scope for repository use:

- `repo`

For managing token scopes (fine-grained token), refer to [the token scopes Reference page](https://charmhub.io/github-runner/docs/reference-token-scopes).

By using [`juju config`](https://juju.is/docs/juju/juju-config) to change the [charm configuration token](https://charmhub.io/github-runner/configure#token) the charm unregisters and removes the old self-hosted runners and instantiates new ones.

```shell
juju config <APP_NAME> token=<TOKEN>
```

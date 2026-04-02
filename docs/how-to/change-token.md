# How to change GitHub authentication

The charm supports two authentication methods: a GitHub App or a personal access token (PAT).
See [Authentication and token scopes](https://charmhub.io/github-runner/docs/reference-token-scopes) for required permissions.

## GitHub App authentication

Create a [GitHub App](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app) with the required permissions and install it on the target organization or repository.

Store the App's PEM-encoded private key in a Juju secret:

```shell
juju add-secret github-app-key private-key="$(cat /path/to/private-key.pem)"
```

Note the secret ID from the output (e.g. `secret:abc123def`), then grant it to the charm and configure the App credentials:

```shell
juju grant-secret github-app-key <APP_NAME>
juju config <APP_NAME> \
  github-app-client-id=<CLIENT_ID> \
  github-app-installation-id=<INSTALLATION_ID> \
  github-app-private-key-secret-id=<SECRET_ID>
```

To rotate the private key, update the Juju secret:

```shell
juju update-secret github-app-key private-key="$(cat /path/to/new-private-key.pem)"
```

## Personal access token authentication

Create a new [GitHub Personal Access Token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens).

An example classic token scope for repository use:

- `repo`

For managing token scopes (fine-grained token), refer to [the token scopes Reference page](https://charmhub.io/github-runner/docs/reference-token-scopes).

By using [`juju config`](https://juju.is/docs/juju/juju-config) to change the [charm configuration token](https://charmhub.io/github-runner/configure#token) the charm unregisters and removes the old self-hosted runners and instantiates new ones.

```shell
juju config <APP_NAME> token=<TOKEN>
```

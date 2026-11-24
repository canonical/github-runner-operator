# Authentication and token scopes

The GitHub runner charm supports two authentication methods for interacting with the GitHub API:
a [GitHub App](https://docs.github.com/en/apps) or a
[personal access token (PAT)](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens).

## GitHub App authentication

GitHub App authentication is the recommended approach. It provides fine-grained permissions
and does not tie access to a personal user account.

To configure the charm with a GitHub App, set the following charm configuration options:

- `github-app-client-id`: The App's Client ID (shown on the GitHub App settings page).
- `github-app-installation-id`: The installation ID for the target organization or repository.
- `github-app-private-key-secret-id`: A Juju secret ID containing the App's PEM-encoded private
  key under the `private-key` field.

### Required GitHub App permissions

#### Organizational runners

Organization permissions:

- Self-hosted runners: read & write

Repository permissions:

- Actions: read (required if COS integration is enabled and private repositories exist)
- Administration: read

#### Repository runners

Repository permissions:

- Actions: read (required if COS integration is enabled and the repository is private)
- Administration: read & write
- Metadata: read

## Personal access token authentication

### Fine grained access token scopes

**Note**: In addition to having a token with the necessary permissions, the user who owns the
token also must have admin access to the organization or repository.

#### Organizational runners

The following are the permissions scopes required for the GitHub runners when registering as an
organizational runner.

Organization:

- Self-hosted runners: read & write

Repository:

- Actions: read (required if COS integration is enabled and private repositories exist)
- Administration: read

#### Repository runners

The following are the permissions scopes required for the GitHub runners when registering as a
repository runner.

- Actions: read (required if COS integration is enabled and the repository is private)
- Administration: read & write
- Metadata: read

### Classic personal access token scopes

Depending on whether the charm is used for GitHub organizations or repositories, the following
scopes should be selected when creating a personal access token.

#### Organizational runners

To use this charm for GitHub organizations, the following scopes should be selected:

- `repo`
- `admin:org`

#### Repository runners

To use this charm for GitHub repositories, the following scopes should be selected:

- `repo`

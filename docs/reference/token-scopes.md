# Token scopes

In order to use the GitHub runner charm, a personal access token with the necessary permissions
is required.

## Fine grained access token scopes

**Note**: In addition to having a token with the necessary permissions, the user who owns the
token also must have admin access to the organisation or repository.

### Organizational runners

The following are the permissions scopes required for the GitHub runners when registering as an
organisational runner.

Organisation:

- Self-hosted runners: read & write

Repository:

- Actions: read (required if COS integration is enabled and private repositories exist)
- Administration: read

### Repository runners

The following are the permissions scopes required for the GitHub runners when registering as an
repository runner.

- Actions: read (required if COS integration is enabled and the repository is private)
- Administration: read & write
- Metadata: read

## Personal access token scopes

Depending on whether the charm is used for GitHub organisations or repositories, the following scopes
should be selected when creating a personal access token.

### Organizational runners

To use this charm for GitHub organisations, the following scopes should be selected:

- `repo`
- `admin:org`

### Repository runners

To use this charm for GitHub repositories, the following scopes should be selected:

- `repo`
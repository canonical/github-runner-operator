# Token scopes

## Fine grained access token scopes

**Note**: In addition to having a token with the necessary permissions, the user who owns the
token also must have admin access to the organization or repository.

### Organizational Runners

The following are the permissions scopes required for the GitHub runners when registering as an
organizational runner.

Organization:

- Self-hosted runners: read & write

Repository:

- Actions: read (required if COS integration is enabled and private repositories exist)
- Administration: read
- Contents: read (not required if the charm is configured to use OpenStack runners)
- Pull requests: read (not required if the charm is configured to use OpenStack runners)

### Repository Runners

The following are the permissions scopes required for the GitHub runners when registering as an
repository runner.

- Actions: read (required if COS integration is enabled and the repository is private)
- Administration: read & write
- Contents: read (not required if the charm is configured to use OpenStack runners)
- Metadata: read
- Pull requests: read (not required if the charm is configured to use OpenStack runners)

## Personal access token scopes

### Organizational Runners

To use this charm for GitHub organizations, the following scopes should be selected:

- `repo`
- `admin:org`

### Repository Runners

To use this charm for GitHub repositories, the following scopes should be selected:

- `repo`
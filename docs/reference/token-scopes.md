# Token scopes

## Fine grained access token scopes

### Organizational Runners

The following are the permissions scopes required for the GitHub runners when registering as an
organisational runner.

Organisation:

- Self-hosted runners: read & write

Repository:

- Actions: read (required if COS integration is enabled and private repositories exist)
- Administration: read
- Contents: read
- Pull requests: read

### Repository Runners

The following are the permissions scopes required for the GitHub runners when registering as an
repository runner.

- Actions: read (required if COS integration is enabled and the repository is private)
- Administration: read & write
- Contents: read
- Metadata: read
- Pull requests: read

## Personal access token scopes

### Organizational Runners

To use this charm for GitHub organisations, the following scopes should be selected:

- `repo`
- `admin:org`

### Repository Runners

To use this charm for GitHub repositories, the following scopes should be selected:

- `repo`
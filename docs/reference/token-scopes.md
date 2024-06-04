# Token scopes

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

The following are the permissions scopes required for the GitHub runners when registering as an
repository runner.

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
# How to troubleshoot

This guide covers troubleshooting for common issues that users may encounter when working with the GitHub runner charm.

## External contributor workflows

### Workflows not running for external contributors

If workflows are not running for external contributors when `allow-external-contributor=false`:

1. Check the runner logs for authorization errors
2. Verify the user's author association in the GitHub repository

### Workflows running for unexpected users

If you notice workflows running for users who shouldn't have access:

1. Set `allow-external-contributor=false`
2. Review repository collaborator permissions
3. Check for any bypass rules in branch protection settings
4. Audit recent workflow runs in the GitHub Actions tab

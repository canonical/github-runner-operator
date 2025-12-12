# How to manage external contributors securely

According to GitHub, running code inside the GitHub self-hosted runner [poses a significant security risk of arbitrary code execution](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners#self-hosted-runner-security). The self-hosted runners managed by the charm are isolated in their own single-use virtual machine instances. In addition, the charm provides security controls to ensure that code from external contributors is only executed when authorized.

The charm provides the `allow-external-contributor` configuration option to control whether workflows triggered by external contributors can execute on the self-hosted runners. When set to `false`, only users with COLLABORATOR, MEMBER, or OWNER status can trigger workflows.

In this guide, we'll explain how to configure external contributor access and recommended security practices.

## External contributor access control

The charm checks the GitHub author association for the following events that can be triggered by external contributors:

- `pull_request` - Pull requests from external contributors
- `pull_request_target` - Pull request targeting (designed for handling PRs from forks)
- `pull_request_review` - Pull request reviews from external contributors
- `pull_request_review_comment` - Comments on pull request diffs from external contributors
- `issue_comment` - Comments on issues or pull requests from external contributors

### Disabling external contributor access

To prevent external contributors from triggering workflows:

```bash
juju config github-runner allow-external-contributor=false
```

With this setting, only users with the following GitHub author associations can trigger workflows:

- `OWNER` - Repository or organization owners
- `MEMBER` - Organization members
- `COLLABORATOR` - Users with explicit collaborator access

### Enabling external contributor access

To allow all external contributors to trigger workflows:

```bash
juju config github-runner allow-external-contributor=true
```

**Warning**: This setting allows any external contributor to trigger workflow execution on your self-hosted runners. Only use this in trusted environments or when you have other security controls in place.

## Recommended security practices

When working with external contributors, consider the following security practices:

### Repository configuration

- For outside collaborators, set permissions to read-only. See [here](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/managing-teams-and-people-with-access-to-your-repository#changing-permissions-for-a-team-or-person) for instructions to change collaborator permissions.

### Branch protection rules

Create the following branch protection rules using the instructions [here](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule#creating-a-branch-protection-rule):

- Branch name pattern `**` with `Require signed commits` enabled.
- Branch name pattern matching only the default branch of the repository, such as `main`, with the following enabled:
  - `Dismiss stale pull request approvals when new commits are pushed`
  - `Required signed commits`
  - `Do not allow bypassing the above settings`

### Working with external contributors

When `allow-external-contributor` is set to `false`, external contributors can still contribute through the following workflow:

1. External contributors create pull requests as usual
2. A repository maintainer with COLLABORATOR, MEMBER, or OWNER status reviews the code
3. If the code is safe, the maintainer can:

- Approve and merge the pull request to another branch (workflows will run with the maintainer's permissions)
- Manually trigger workflow runs if needed (using workflow dispatch on the target branch)

This approach ensures that all code from external contributors is reviewed by trusted users before execution on self-hosted runners.

## Troubleshooting

This section covers troubleshooting for common issues that users may encounter.

### Workflows not running for external contributors

If workflows are not running for external contributors when `allow-external-contributor=false`:

1. Check the runner logs for authorization errors
2. Verify the user's author association in the GitHub repository

### Workflows running for untrusted users

If you notice workflows running for users who shouldn't have access:

1. Set `allow-external-contributor=false`
2. Review repository collaborator permissions
3. Check for any bypass rules in branch protection settings
4. Audit recent workflow runs in the GitHub Actions tab

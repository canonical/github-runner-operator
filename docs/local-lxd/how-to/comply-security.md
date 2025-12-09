# How to comply with security requirements

According to GitHub, running code inside the GitHub self-hosted runner [poses a significant security risk of arbitrary code execution](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners#self-hosted-runner-security). The self-hosted runners managed by the charm are isolated in its own single-use virtual machine instance. In addition, the charm enforces some repository settings to ensure all code running on the self-hosted runners is reviewed by someone trusted.

The charm provides the `allow-external-contributor` configuration option to control whether workflows triggered by external contributors can execute on the self-hosted runners. When set to `false`, only users with COLLABORATOR, MEMBER, or OWNER status can trigger workflows from pull requests, reviews, and comments.

In this guide, a recommended set of policies and security practices will be presented.

## External contributor access control

Configure the charm to restrict external contributor access:

```bash
juju config github-runner allow-external-contributor=false
```

With this setting, workflows will only run for users with the following GitHub author associations:
- `OWNER` - Repository or organization owners
- `MEMBER` - Organization members  
- `COLLABORATOR` - Users with explicit collaborator access

The charm checks author associations for these events:
- `pull_request` - Pull requests from external contributors
- `pull_request_target` - Pull request targeting (designed for handling PRs from forks)
- `pull_request_review` - Pull request reviews from external contributors
- `pull_request_review_comment` - Comments on pull request diffs from external contributors
- `issue_comment` - Comments on issues or pull requests from external contributors

## Recommended policy

- For outside collaborators the permission should be set to read. See [here](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/managing-teams-and-people-with-access-to-your-repository#changing-permissions-for-a-team-or-person) for instructions to change collaborator permissions. Outside collaborators will still be able to contribute with pull requests, but reviews will be needed. Details in a later section.
- Create the following branch protection rules, with the instructions [here](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule#creating-a-branch-protection-rule):
  - branch name pattern `**` with `Require signed commits` enabled.
  - branch name pattern matching only the default branch of the repository, such as `main`, with the follow enabled:
    - `Dismiss stale pull request approvals when new commits are pushed`
    - `Required signed commits`
    - `Do not allow bypassing the above settings`

With these settings, the common workflow of creating branches with pull requests and merging to the default branch is supported. Other GitHub Actions workflow triggers such as `workflow_dispatch`, `push`, and `schedule` are supported as well.

### Working with outside collaborators

When `allow-external-contributor` is set to `false`, outside collaborators can still contribute through the following secure workflow:

1. External contributors create pull requests as usual
2. A repository maintainer with COLLABORATOR, MEMBER, or OWNER status reviews the code
3. If the code is safe, the maintainer can:
  - Approve and merge the pull request to another branch (workflows will run with the maintainer's permissions)
  - Manually trigger workflow runs if needed (via workflow dispatch on the target branch)

This approach ensures that all code from external contributors is reviewed by trusted users before execution on self-hosted runners, eliminating the need for manual comment-based approval workflows.

## Migration from repo-policy-compliance

If you were previously using the repo-policy-compliance functionality, the `allow-external-contributor` configuration provides similar security controls:

1. Update your charm configuration to use `allow-external-contributor=false`
2. Verify that external contributor workflows are properly restricted

The new approach provides broader security coverage and simpler configuration compared to the previous policy compliance system.

# How to manage external contributors securely

According to GitHub, running code inside the GitHub self-hosted runner [poses a significant security risk of arbitrary code execution](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners#self-hosted-runner-security). The self-hosted runners managed by the charm are isolated in their own single-use virtual machine instances. In addition, the charm provides security controls to ensure that code from external contributors is only executed when authorized.

The charm provides the `allow-external-contributor` configuration option to control whether workflows triggered by external contributors can execute on the self-hosted runners. When set to `false`, only users with COLLABORATOR, MEMBER, or OWNER status can trigger workflows.

In this guide, we'll explain how to configure external contributor access.

## External contributor access control

An external contributor is anyone whose GitHub author association is not OWNER, MEMBER, or COLLABORATOR. For internal pull requests (where the head and base repositories are the same), the association check is not applied; those runs are treated as internal.

The charm checks the GitHub author association for the following events that can be triggered by external contributors:

- `pull_request` - Pull requests from external contributors
- `pull_request_target` - Pull request targeting (designed for handling PRs from forks)
- `pull_request_review` - Pull request reviews from external contributors
- `pull_request_review_comment` - Comments on pull request diffs from external contributors
- `issue_comment` - Comments on issues or pull requests from external contributors

### Disable external contributor access

Prevent external contributors from triggering workflows. Run:

```bash
juju config github-runner allow-external-contributor=false
```

With this setting, only users with the following GitHub author associations can trigger workflows:

- OWNER - Repository or organization owners
- MEMBER - Organization members
- COLLABORATOR - Users with explicit collaborator access

### Enable external contributor access

Allow all external contributors to trigger workflows. Run:

```bash
juju config github-runner allow-external-contributor=true
```

**Warning**: This setting allows any external contributor to trigger workflow execution on your self-hosted runners. Only use this in trusted environments or when you have other security controls in place.

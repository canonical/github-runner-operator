# How to comply with security requirements

According to GitHub, running code inside the GitHub self-hosted runner [poses a significant security risk of arbitrary code execution](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners#self-hosted-runner-security). The self-hosted runners managed by the charm are isolated in its own single-use virtual machine instance. In addition, the charm enforces some repository settings to ensure all code running on the self-hosted runners is reviewed by someone trusted.

The charm can be integrated with the [Repo Policy Compliance charm](https://charmhub.io/repo-policy-compliance) to enforce a set of good practices around GitHub repository settings. Self-hosted runners managed by the charm will not run jobs on repositories unless they are compliant with the practices.

In this guide, a recommended set of policies will be presented.

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

Generally, outside collaborators are not completely trusted, but still would need to contribute in some manner. As such, this charm requires pull requests by outside collaborators to be reviewed by someone with `write` permission or above. Once the review is completed, the reviewer should add a comment including the following string: `/canonical/self-hosted-runners/run-workflows <commit SHA>`, where `<commit SHA>` is the commit SHA of the approved commit. Once posted, the self-hosted runners will run the workflow for this commit.

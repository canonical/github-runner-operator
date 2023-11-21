# How to comply with security requirements

[Running GitHub self-hosted runner poses security risk, such as, arbitrary code execution according to GitHub](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners#self-hosted-runner-security). Like GitHub the self-hosted runners managed by the charm are isolated in its own single-use virtual machine instance. In addition, the charm enforce some repository settings to ensure all code running on the self-hosted runners are reviewed by someone trusted.

The repository settings enforced with this [Python library](https://github.com/canonical/repo-policy-compliance). The rules enforce are different depending on how the GitHub Actions workflow is triggered. The README of the python library details the policies it enforces for different type of trigger.

For this guide, a recommended set of policy will be presented, but any set repository settings that passes the [Python library](https://github.com/canonical/repo-policy-compliance) checks will work with the self-hosted runners managed by this charm.

## Recommended policy

- For outside collaborators the permission should be set to read. See [here](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/managing-teams-and-people-with-access-to-your-repository#changing-permissions-for-a-team-or-person) for instruction to change collaborator permissions. Outside collaborators will still be able to contribute with pull requests, but reviews will be needed. Details in a later section.
- Create the following branch protection rules, with the instructions [here](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule#creating-a-branch-protection-rule):
  - branch name pattern `**` with `Require signed commits` enabled.
  - branch name pattern matching only the default branch of the repository, such as `main`, with the follow enabled:
    - `Dismiss stale pull request approvals when new commits are pushed`
    - `Required signed commits`
    - `Do not allow bypassing the above settings`

With these settings, the common workflow of creating branches with pull requests and merging to the default branch is supported. Other GitHub Actions workflow triggers such as workflow_dispatch, push, and schedule are supported as well.

### Working with outside collaborators

Generally, outside collaborators are someone that is not completely trusted, but still would need to contribute in some manner. As such, this charm requires pull request by outside collaborators to be reviewed by someone with `write` or above permission with the repository. Once the review is completed, the reviewer should add a comment that includes the following string: `/canonical/self-hosted-runners/run-workflows <commit SHA>`. Where `<commit SHA>` is the commit SHA of the approved commit. Once that is done, the self-hosted runners managed by this charm will be able to run the workflow on this commit.

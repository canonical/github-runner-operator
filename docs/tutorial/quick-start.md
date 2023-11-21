# Quick start

## What you'll do

- Setup a GitHub repository
- Activate the GitHub APIs related to self-hosted runner
- Deploy the [GitHub runner charm](https://charmhub.io/github-runner)
- Ensure GitHub repository setting are secure
- Run a simple workflow on the self-hosted runner

## Requirements

- GitHub Account.
- Juju 3 installed.
- Juju controller on OpenStack, and a juju model.

For more information about how to install and use Juju, see [Get started with Juju](https://juju.is/docs/olm/get-started-with-juju).

## Steps

### Create GitHub repositry

The GitHub self-hosted runner spawned by the charm needs to connect to a GitHub repository or organization. GitHub repositories are used as it is simpler to manage.

To create a GitHub repository, log in to [GitHub](https://github.com) with your GitHub Account and follow the instruction [here](https://docs.github.com/en/get-started/quickstart/create-a-repo#create-a-repository). For this tutorial, create a public repository as [GitHub branch protection rules is only available in public repository with GitHub Free tier](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule).

### Activate GitHub APIs related to self-hosted runner

***This must be done for GitHub runner charm to function correctly.***

The GitHub runner charm uses GitHub APIs related to self-hosted runners. Some of the APIs will only be functional after a self-hosted runner registration token is requested for the repository for the first time. If a registration token is requested for the repository before then this can be skipped.

The registration token can be requested by calling the [GitHub API to request a self-hosted runner registration token](https://docs.github.com/en/rest/actions/self-hosted-runners?apiVersion=2022-11-28#create-a-registration-token-for-a-repository). Alternatively, a registration token can be requested by visiting the "New self-hosted runner" page for the repository (`https://github.com/{OWNER}/{REPO}/settings/actions/runners/new`). This can be done by following the instruction to the 4th step provided [here](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/adding-self-hosted-runners#adding-a-self-hosted-runner-to-a-repository).

### Deploy the GitHub runner charm

The charm requires a GitHub personal access token with `repo` access, which can be created with the instructions [here](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-personal-access-token-classic).

Once the personal access token is created, the charm can be deployed with:

```shell
juju deploy github-runner --constraints="cores=4 mem=16G" --config token=<TOKEN> --config path=<OWNER/REPO>
```

Replacing the `<TOKEN>` with the personal access token, and `<OWNER/REPO>` the GitHub account name and GitHub repository separated with `/`.

The `--constraints` option for the `juju deploy` set the resource used for the juju machine hosting the charm application. This is used to accommodate different size of self-hosted runner.

Once the charm is active status, visit the runner page for the GitHub repository (`https://github.com/{OWNER}/{REPO}/settings/actions/runners`) according to the instructions [here](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/using-self-hosted-runners-in-a-workflow#viewing-available-runners-for-a-repository). A single new runner should be available as it is the default number of self-hosted runners created.

The charm would regularly goes into maintain status to managed the self-hosted runners. For example, replacing a self-hosted runner that was used up by a GitHub Actions job.

### Ensure GitHub repository settings are secure

For public repository, [arbitrary code execution with the self-hosted runners are possible](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners#self-hosted-runner-security). To combat this, the charm enforce a set of setting for the repository to ensure the code executed in the self-hosted runner are reviewed by someone trusted.

Create a branch protection rule with the branch name pattern `**` and enable `Require signed commits` by following the instructions [here](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule#creating-a-branch-protection-rule).

### Run a simple workflow on the self-hosted runner

Once the self-hosted runner is available on GitHub, it can be used to run GitHub Actions jobs similiar to runners provided by GitHub. The only difference being the label specified in the `runs-on` of a job.

The self-hosted runner managed by the charm would have the following labels: `self-hosted`, `linux`, and the application name

In the above deployment, the application name was not specified hence the default value of `github-runner` was used. As such, `github-runner` would be a label for the self-hosted runner managed by the application instance.

To test out the self-hosted runner, create the following file under the path `.github/workflows/runner_test.yaml` in the locally cloned git repository of the created GitHub repository with the following content:

```yaml
name: Runner test

on:
  push:

jobs:
  hello-world-test:
    runs-on: [self-hosted, github-runner]
    steps:
        - run: echo "hello world"
```

Create a commit with this file and push it to GitHub.

Under the `Actions` tab of the GitHub repository, the workflow run should appear after a while. The workflow should complete successfully.

#### Removing the charm

The charm and the self-hosted runners can be removed with the following command:

```shell
juju remove-application github-runner
```

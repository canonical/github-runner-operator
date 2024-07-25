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
- Juju controller on OpenStack or LXD (see [How to run on LXD cloud](https://charmhub.io/github-runner/docs/how-to-run-on-lxd)) and a juju model.

For more information about how to install and use Juju, see [Get started with Juju](https://juju.is/docs/olm/get-started-with-juju).

## Steps

### Create GitHub repository

The GitHub self-hosted runner spawned by the charm needs to connect to a GitHub repository or organization. GitHub repositories are used as it is simpler to manage.

To create a GitHub repository, log in to [GitHub](https://github.com) with your GitHub Account and follow the instructions [here](https://docs.github.com/en/get-started/quickstart/create-a-repo#create-a-repository). For this tutorial, create a public repository as [GitHub branch protection rules is only available in public repository with GitHub Free tier](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule).

### Activate GitHub APIs related to self-hosted runner

***This must be done for the GitHub runner charm to function correctly.***

The GitHub runner charm relies on GitHub APIs for self-hosted runners. Some of the APIs will only be functional after a self-hosted runner registration token is requested for the repository for the first time.

The registration token can be requested by calling the [GitHub API](https://docs.github.com/en/rest/actions/self-hosted-runners?apiVersion=2022-11-28#create-a-registration-token-for-a-repository). Alternatively, it can also be requested by visiting the "New self-hosted runner" page for the repository (`https://github.com/{OWNER}/{REPO}/settings/actions/runners/new`). This can be done by following the instruction to the 4th step provided [here](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/adding-self-hosted-runners#adding-a-self-hosted-runner-to-a-repository).

### Deploy the GitHub runner charm

The charm requires a GitHub personal access token with `repo` access, which can be created following the instructions [here](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-personal-access-token-classic).
A user with `admin` access for the repository/org is required, otherwise, the repo-policy-compliance will fail the job.
For information on token scopes, see [How to change GitHub personal access token](how-to/change-token.md).

Once the personal access token is created, the charm can be deployed with:

```shell
juju deploy github-runner --constraints="cores=4 mem=16G root-disk=20G virt-type=virtual-machine" --config token=<TOKEN> --config path=<OWNER/REPO> --config runner-storage=memory --config vm-memory=2GiB --config vm-disk=10GiB
```

Replacing the `<TOKEN>` with the personal access token, and `<OWNER/REPO>` the GitHub account name and GitHub repository separated with `/`.

The `--constraints` option for the `juju deploy` sets the resource requirements for the juju machine hosting the charm application. This is used to accommodate different sizes of self-hosted runners. For details, refer to [Managing resource usage](https://charmhub.io/github-runner/docs/tutorial-managing-resource-usage).

The `--storage` option mounts a juju storage to be used as the disk for LXD instances hosting the self-hosted runners. Refer [How to configure runner storage](https://charmhub.io/github-runner/docs/how-to-configure-runner-storage) for more information.

The charm performs various installation and configuration on startup. The charm might upgrade the kernel of the juju machine and reboot the juju machine. During reboot, the juju machine will go into the `down` state, this is a part of the normal reboot process and the juju machine should be restarted after a while.

Once the charm reaches active status, visit the runner page for the GitHub repository (`https://github.com/{OWNER}/{REPO}/settings/actions/runners`) according to the instructions [here](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/using-self-hosted-runners-in-a-workflow#viewing-available-runners-for-a-repository). A single new runner should be available as it is the default number of self-hosted runners created.

The charm will spawn new runners on a schedule. During this time, the charm will enter maintenance status.

### Run a simple workflow on the self-hosted runner

Once the self-hosted runner is available on GitHub, it can be used to run GitHub Actions jobs similar to runners provided by GitHub. The only difference being the label specified in the `runs-on` of a job.

The self-hosted runner managed by the charm will have the following labels: `self-hosted`, `linux`, and the application name.

In the above deployment, the application name was not specified, hence the default value of `github-runner` was used. As such, `github-runner` will be a label for the self-hosted runner managed by the application instance.

To test out the self-hosted runner, create the following file under the path `.github/workflows/runner_test.yaml` in the repository with the following content:

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

Upon pushing the changes, under the `Actions` tab of the GitHub repository, the workflow run should appear after a while. The workflow should complete successfully.

If the workflow failed at the `Set up runner` step with the following message:

> This job has failed to pass a repository policy compliance check as defined in the https://github.com/canonical/repo-policy-compliance repository. The specific failure is listed below. Please update the settings on this project to fix the relevant policy.

The repository setting does not comply with the best practice enforce by the charm. See [How to comply with repository policies](https://charmhub.io/github-runner/docs/how-to-repo-policy).

#### Removing the charm

The charm and the self-hosted runners can be removed with the following command:

```shell
juju remove-application github-runner
```

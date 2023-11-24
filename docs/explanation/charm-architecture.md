# Charm architecture

A [Juju](https://juju.is/) [charm](https://juju.is/docs/olm/charmed-operators) to operate a set of [GitHub self-hosted runners](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners) while managing the security and resource usage.

Conceptually, the charm can be divided into the following:

- Management of LXD ephemeral virtual machines to host [ephemeral self-hosted runners](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/autoscaling-with-self-hosted-runners#using-ephemeral-runners-for-autoscaling).
- Management of a [Python web service for checking GitHub repository settings](https://github.com/canonical/repo-policy-compliance).

## LXD ephemeral virtual machines

 To ensure a clean and isolated environment for every runner, self-hosted runners use LXD virtual machines. The charm spawns virtual machines setting resources based on charm configurations. The self-hosted runners start with the ephemeral option and will clean themselves up once the execution has finishes, freeing the resources.

## GitHub repository setting check

A [flask application](https://flask.palletsprojects.com/) hosted on [gunicorn](https://gunicorn.org/) provides a RESTful HTTP API to check the settings of GitHub repository. This ensures the GitHub repository settings do not allow the execution of code not reviewed by maintainers on the self-hosted runners.

Using the [pre-job script](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/running-scripts-before-or-after-a-job#about-pre--and-post-job-scripts), the self-hosted runners calls the Python web service to check if the GitHub repository settings for the job are compliant. If not compliant, it will output an error message and force stop the runner to prevent code from being executed.

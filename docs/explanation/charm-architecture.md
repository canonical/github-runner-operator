# Charm architecture

A [Juju](https://juju.is/) [charm](https://juju.is/docs/olm/charmed-operators) is a set of Python scripts and libraries that operates some software. This charm operates a set of [GitHub self-hosted runners](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners) while handling the security and hardware management.

Conceptually, the charm can be divided into the following:

- Management of LXD ephemeral virtual machines to host [ephemeral self-hosted runners](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/autoscaling-with-self-hosted-runners#using-ephemeral-runners-for-autoscaling).
- Management of a [Python web service for checking GitHub repository settings](https://github.com/canonical/repo-policy-compliance).

## LXD ephemeral virtual machines

Using LXD ephemeral virtual machines to host the self-hosted runners ensures the environment is clean and isolated. The charm spawns a set of virtual machines with resources configured according to the charm configurations. The self-hosted runners are started with the ephemeral option and would clean up itself once it has taken a job from GitHub. At the end of the execution of the self-hosted runners application, the LXD ephemeral virtual machines would stop itself and clean up its resources. Freeing the resources to be used by future instances of virtual machines.

## GitHub repository setting check

A [flask application](https://flask.palletsprojects.com/) hosted on [gunicorn](https://gunicorn.org/) provides RESTful HTTP API to check the settings of GitHub repository. This is intended to ensure the GitHub repository settings does not allow for execution of untrusted code on the self-hosted runners managed by this charm.

Using the [pre-job script](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/running-scripts-before-or-after-a-job#about-pre--and-post-job-scripts), the self-hosted runners managed by this charm would call the Python web service to check if the GitHub repository setting for the job it is about to execute are compliant. If the web service determines the repository settings has errors, it would output a error message and force stop the runner to prevent untrusted code from executing.

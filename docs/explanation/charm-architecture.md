# Charm architecture

A [Juju](https://juju.is/) [charm](https://juju.is/docs/olm/charmed-operators) to operate a set of [GitHub self-hosted runners](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners) while managing security and resource usage.

Conceptually, the charm can be divided into the following:

- Management of LXD ephemeral virtual machines to host [ephemeral self-hosted runners](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/autoscaling-with-self-hosted-runners#using-ephemeral-runners-for-autoscaling)
- Management of the network
- GitHub API usage
- Management of [Python web service for checking GitHub repository settings](https://github.com/canonical/repo-policy-compliance)
- Management of dependencies

## LXD ephemeral virtual machines

To ensure a clean and isolated environment for every runner, self-hosted runners use LXD virtual machines. The charm spawns virtual machines, setting resources based on charm configurations. The self-hosted runners start with the ephemeral option and will clean themselves up once the execution has finished, freeing the resources. This is [similar to how GitHub hosts their runners due to security concerns](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/about-self-hosted-runners#self-hosted-runner-security). 

As the virtual machines are single-use, the charm will replenish virtual machines on a regular schedule. This time period is determined by the [`reconcile-interval` configuration](https://charmhub.io/github-runner/configure#reconcile-interval).

On schedule or upon configuration change, the charm performs a reconcile to ensure the number of runners managed by the charm matches the [`virtual-machines` configuration](https://charmhub.io/github-runner/configure#virtual-machines), and the resources used by the runners match the various resource configurations.

The virtual machines hosting the runner use random access memory as disk; therefore, the [`vm-disk` configuration](https://charmhub.io/github-runner/configure#vm-disk) can impact the memory usage of the Juju machine. This is done to prevent disk IO exhaustion on the Juju machine on disk-intensive GitHub workflows. In the future, an alternative method to prevent disk IO exhaustion will be implemented.

## Network configuration

The charm respects the proxy configuration passed from Juju in the following environment variables: `JUJU_CHARM_HTTP_PROXY`, `JUJU_CHARM_HTTPS_PROXY`, and `JUJU_CHARM_NO_PROXY`. The GitHub self-hosted runner applications are configured to use the proxy configuration.

If an HTTP(S) proxy is used, all HTTP(S) requests in the GitHub workflow will be routed to the proxy automatically with [aproxy](https://github.com/canonical/aproxy). The service is installed on each runner virtual machine and configured according to the proxy configuration from Juju.

The firewall is configured to deny traffic from the runner to IPs on the [`denylist` configuration](https://charmhub.io/github-runner/configure#denylist). The runner will always have access to essential services such as DHCP and DNS, regardless of the denylist configuration.

## GitHub API usage

The charm requires a GitHub personal access token for the [`token` configuration](https://charmhub.io/github-runner/configure#token). This token is used for:

- Requesting self-hosted runner registration tokens
- Requesting self-hosted runner removal tokens
- Requesting a list of runner applications
- Requesting a list of self-hosted runners configured in an organization or repository
- Deletion of self-hosted runners

## GitHub repository setting check

The [repo-policy-compliance](https://github.com/canonical/repo-policy-compliance) is a [Flask application](https://flask.palletsprojects.com/) hosted on [Gunicorn](https://gunicorn.org/) that provides a RESTful HTTP API to check the settings of GitHub repositories. This ensures the GitHub repository settings do not allow the execution of code not reviewed by maintainers on the self-hosted runners.

Using the [pre-job script](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/running-scripts-before-or-after-a-job#about-pre--and-post-job-scripts), the self-hosted runners call the Python web service to check if the GitHub repository settings for the job are compliant. If not compliant, it will output an error message and force stop the runner to prevent code from being executed.

## Dependencies management

Upon installing or upgrading the charm, the kernel will be upgraded, and the Juju machine will be restarted if needed.

The charm installs the following dependencies and regularly updates them:

- Gunicorn
- Nftables
- LXD
- Cpu-checker
- Libvirt-clients
- Libvirt-daemon-driver-qemu
- Apparmor-utils
- Repo-policy-compliance
- GitHub self-hosted runner application

The charm ensures the above dependencies are updated prior to creating new virtual machines for runners.

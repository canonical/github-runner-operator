# Security in GitHub runner charm

This document describes the security design of the GitHub runner charm. The charm managed a set of GitHub self-hosted runners. The GitHub self-hosted runners allow CI/CD jobs on GitHub to run on virtual machines managed by the charm. The charm supports various features with security implications.

## Remote code execution risk

The charm manages GitHub self-hosted runners to run GitHub Actions jobs. This allows users on GitHub to execute code on the servers hosting the runners. This poses a remote code execution risk if the code is not trusted. Therefore, the charm should only spawn runners to trusted organization or trusted repository.

For third-party contribution, the charm can integrate with [Repo Policy Compliance charm](https://charmhub.io/repo-policy-compliance) to manage the repository policy. With this integration, the self-hosted runner will not execute the GitHub jobs if the policy is not met. See [working with outside collaborators](https://charmhub.io/github-runner/docs/how-to-comply-security#working-with-outside-collaborators) for the recommended settings to ensure the code is reviewed by a trusted user prior to execution in the runner.

### Good practices

- Only register the GitHub self-hosted runners to a trusted organization or repository. So that only workflow from trusted users are able to run on the runners.
- For outside collaborators Use [Repo Policy Compliance charm](https://charmhub.io/repo-policy-compliance) to with [policy for outside collaborators](https://charmhub.io/github-runner/docs/how-to-comply-security#working-with-outside-collaborators) to ensure the code executed in runners are reviewed by a trusted user.

## Permission for GitHub app or personal access token

The charm interacts with GitHub via RESTful API. This requires a [personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens).

It is generally recommended to grant the minimal permissions necessary for security reasons. Use [fine-grained token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-fine-grained-personal-access-token) to control the scope of permission. See [token scopes](https://charmhub.io/github-runner/docs/reference-token-scopes).

### Good practices

- Use fine-grained personal access token.
- Give the minimal permission required. See [token scopes](https://charmhub.io/github-runner/docs/reference-token-scopes).

## OpenStack project management

The charm spawns [OpenStack servers](https://docs.openstack.org/python-openstackclient/train/cli/command-objects/server.html) to host the [GitHub self-hosted runner application](https://github.com/actions/runner). Since the GitHub jobs runs within the OpenStack servers, it is recommanded to isolate these OpenStack servers in its own [OpenStack project](https://docs.openstack.org/python-openstackclient/pike/cli/command-objects/project.html). This prevents GitHub jobs from accessing other resources by isolating them in their own OpenStack project See [here](https://docs.openstack.org/keystone/pike/admin/cli-manage-projects-users-and-roles.html) on how to manage OpenStack projects and users. See [spawning OpenStack runner](https://charmhub.io/github-runner/docs/how-to-openstack-runner) for how to make the charm utilize the OpenStack user and project.

### Good practices

- Have a separate OpenStack user and OpenStack project for the self-hosted runner to use.

## Proxied environment

It is common for enterprise or to manage outgoing network traffic through HTTP(S) proxies. By funnelling all outgoing traffic through a proxy, there is a single point to control and observe the network traffic for administrators. If the OpenStack server hosting the runners is in such an environment, the GitHub workflow would have to adopt to route all traffic through the HTTP(S) proxies. Many popular GitHub Actions were designed to be ran on the GitHub provided runners which is not in a proxied environment. Hence many GitHub Actions do not work with HTTP(S) proxies.

To address this issue, the charm utilizes [aproxy](https://github.com/canonical/aproxy), a service that routes outgoing network traffic to a configured endpoint. The charm uses aproxy to transparently route outgoing traffic through the configured HTTP(S) proxy, ensuring that GitHub Actions work out of the box in a proxied environment. GitHub actions should work out of the box in a proxied environment with this. Aproxy can be enabled via [a charm configuration](https://charmhub.io/github-runner/configurations#experimental-use-aproxy).

### Good practices

- Manage the outgoing network traffic with a HTTP(S) proxy.
- Use aproxy to make GitHub Actions work transparently with HTTP(S) proxy.

## OpenStack server network traffic

The charm spawns OpenStack servers to host the GitHub self-hosted runner application. The charm has taken pre-caution to manage the access of the OpenStack servers hosting the runner application. OpenStack security group is used to manage the egress and ingress traffic. The OpenStack server is able to:

- Receive traffic on port 22. Needed for the charm to manage the OpenStack server.
- Send traffic on port 10022. Needed for the integration with [tmate-ssh-server charm](https://charmhub.io/tmate-ssh-server)

Other OpenStack security rules can be enforced by the OpenStack host. Enabling all port for egress is a common default OpenStack security rule. The above is what the charm manages.

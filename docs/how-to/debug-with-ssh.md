# How to debug with ssh

The charm exposes an integration `debug-ssh` interface which can be used with
[tmate-ssh-server charm](https://charmhub.io/tmate-ssh-server/) to pre-configure runners with
environment variables to be picked up by [action-tmate](https://github.com/canonical/action-tmate/)
for automatic configuration.

## Prerequisites

To enhance the security of self-hosted runners and its infrastracture, only authorized connections
can be established. Hence, action-tmate users must have
[ssh-key registered](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account)
on the GitHub account.

## Deploying

Use the following command to deploy and integrate github-runner with tmate-ssh-server.

```shell
juju deploy tmate-ssh-server
juju integrate tmate-ssh-server github-runner
```

Idle runners will be flushed and restarted. Busy runners will be configured automatically on next
spawn.

## Using the action

Create a workflow that looks like the following within your workflow to enable action-tmate.

```yaml
name: SSH Debug workflow example

on: [pull_request]

jobs:
  build:
    runs-on: [self-hosted]
    steps:
    - uses: actions/checkout@v3
    - name: Setup tmate session
      uses: canonical/action-tmate@main
```

The output of the action looks like the following.

```
<workflow setup logs redacted>
SSH: ssh -p 10022 <user>@<ip>
or: ssh -i <path-to-private-SSH-key> -p10022 <user>@<ip>
```

Read more about [action-tmate's usage here](https://github.com/canonical/action-tmate).
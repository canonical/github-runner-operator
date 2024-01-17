# SSH Debug

To enhance the security of the runner and the infrastructure behind the runner, only user ssh-keys
registered on [Authorized Keys](https://github.com/tmate-io/tmate-ssh-server/pull/93) are allowed
by default on [tmate-ssh-server charm](https://charmhub.io/tmate-ssh-server/).

Authorized keys are registered via [action-tmate](https://github.com/canonical/action-tmate/)'s
`limit-access-to-actor` feature. This feature uses GitHub users's SSH key to launch an instance
of tmate session with `-a` option, which adds the user's SSH key to `~/.ssh/authorized_keys`.

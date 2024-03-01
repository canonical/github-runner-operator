# SSH Debug

SSH debugging allows a user to identify and resolve issues or errors that occur through the secure
shell (SSH) connection between a client and a server.

To enhance the security of the runner and the infrastructure behind the runner, only user ssh-keys
registered on [Authorized Keys](https://github.com/tmate-io/tmate-ssh-server/pull/93) are allowed
by default on [tmate-ssh-server charm](https://charmhub.io/tmate-ssh-server/).

Authorized keys are registered via [action-tmate](https://github.com/canonical/action-tmate/)'s
`limit-access-to-actor` feature. This feature uses GitHub users's SSH key to launch an instance
of tmate session with `-a` option, which adds the user's SSH key to `~/.ssh/authorized_keys`.

### Firewall rules

By default, if there are any overlapping IPs within the `denylist` config option with the IP
assigned to `tmate-ssh-server`, an exception to that IP will be made so that the `debug-ssh`
relation can be setup correctly.

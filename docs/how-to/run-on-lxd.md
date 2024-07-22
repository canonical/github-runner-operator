# How to run on LXD cloud

This machine charm needs to run on virtual machines with nested virtualization enabled.

By default, juju machines on LXD are containers.

To run this charm on LXD, add `virt-type=virtual-machine` to the constraints during deployment:

```shell
juju deploy github-runner --constraints="cores=2 mem=16G virt-type=virtual-machine" \
--config token=<TOKEN> --config path=<OWNER/REPO>
```

This constraint ensures the juju machine hosting the charm is a LXD virtual machine. See
[Managing resource usage](https://charmhub.io/github-runner/docs/managing-resource-usage) for
recommendation on `cores` and `mem` constraint.

### Notes

The name of the application must not be longer than 29 characters. This is due to the nature of LXD
pathing that must not exceed 108 bytes. 79 characters are reserved for path naming convention.
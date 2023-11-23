# How to run on LXD cloud

This machine charm needs to run on virtual machines with nested virtualization enabled.

By default, juju machine on LXD are containers.

To run this charm on LXD, add `virt-type=virtual-machine` to the constraints during deployment:

```shell
juju deploy github-runner --constraints="cores=4 mem=16G virt-type=virtual-machine" --config token=<TOKEN> --config path=<OWNER/REPO>
```

This constraint ensure the juju machine hosting the charm is a LXD virtual machine.

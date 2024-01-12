
# How to configure runner storage

To prevent GitHub Action job from exhausting the disk IO of the juju machine hosting the charm, the charm provides two storage options to be configured as the LXD instance root disk:

- Random access memory as disk
- Storage provided by juju

This is configured with the [`runner-storage`](https://charmhub.io/github-runner/configure#runner-storage) option. The configuration should be set during deployment and cannot be changed.

## Random access memory as disk

The random access memory of the juju machine is configured as LXD storage and used as the root disk for the LXD instances.

The `runner-storage` configuration needs to be set to `memory` during deployment, and the juju machine constraints should have enough memory for the virtual machine memory and disk. See [Managing resource usage](https://charmhub.io/github-runner/docs/managing-resource-usage).

An example deployment:

```shell
juju deploy github-runner --constraints="cores=4 mem=12G root-disk=20G virt-type=virtual-machine" --config token=<TOKEN> --config path=<OWNER/REPO> --config runner-storage=memory --config vm-memory=2GiB --config vm-disk=6GiB
```

## Storage provided by juju

The juju storage needs to be mounted during deployment, and the `runner-storage` configuration should be set to `juju-storage` during deployment.

An example deployment:

```shell
juju deploy github-runner --constraints="cores=4 mem=6G root-disk=26G virt-type=virtual-machine" --config token=<TOKEN> --config path=<OWNER/REPO> --config runner-storage=juju-storage --config vm-memory=2GiB --config vm-memory=6GiB --storage runner=rootfs
```

The above example uses `rootfs`, which is using the root disk of the juju machine. Hence the root-disk size was increase to 26G.
In production environment, a separated storage managed by juju should be used. See [how to manage juju storage](https://juju.is/docs/juju/manage-storage).

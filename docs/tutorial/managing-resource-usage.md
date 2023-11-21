# Managing resource usage

The charm can be hardware resource instensive. As each instance of self-hosted runner application is hosted in a virtual machine.

## Virtual machine resource usage

The minimum resource usage for a single virtual machine:

- A minimum of 1 [virtual machine vCPU](https://charmhub.io/github-runner/configure#vm-cpu) is required.
- A minimum of 2GiB of [virtual machine memory](https://charmhub.io/github-runner/configure#vm-memory) is required.
- A minimum of 6GiB of [virtual machine disk](https://charmhub.io/github-runner/configure#vm-disk) is required.

## Juju machine resource usage

This charm is a machine charm, and the juju machine would requires some hardware resource.

It is recommended the juju machine has at least 4GiB of memory reserved to itself. Generally, 20GiB of disk is provisioned for the juju machine as the juju logs can take up disk space on the juju machine over time.

The juju machine would also need the enough resource to host the virtual machines. The memory of the juju machine is used as the disk for the virtual machines.

The recommended combined resource usage would be:

- vCPU: Depends on the workload.
- memory: number of virtual machine * (memory per virtual machine + disk per virtual machine) + 4GiB recommended.
- disk: 20GiB recommended.

## Juju machine constraint

During [deployment of the charm](https://juju.is/docs/juju/juju-deploy), the application constraint can be used to specify the juju machine resource usage. For example, `juju deploy github-runner --constraints="cores=4 mem=16G disk=20G"`.

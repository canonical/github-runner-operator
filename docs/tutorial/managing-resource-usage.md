# Managing resource usage

The charm can be hardware intensive, as each instance of self-hosted runner application is hosted in a virtual machine.

## Virtual machine resource usage

The minimum requirements for a single virtual machine are:

- 1 [virtual machine vCPU](https://charmhub.io/github-runner/configure#vm-cpu)
- 2GiB of [virtual machine memory](https://charmhub.io/github-runner/configure#vm-memory)
- 6GiB of [virtual machine disk](https://charmhub.io/github-runner/configure#vm-disk)

## Juju machine resource usage

It is recommended the juju machine has a minimum of 4GiB of memory dedicated to itself. Generally, 20GiB of disk is provisioned for the juju machine for the Juju logs.

The juju machine will also need the enough resources to host the virtual machines. The memory of the juju machine is used as the disk for the virtual machines.

The recommended combined resource usage is:

- vCPU: Depends on the workload
- memory: number of virtual machines * (memory per virtual machine + disk per virtual machine) + 4GiB
- disk: 20GiB

## Juju machine constraints

During [deployment of the charm](https://juju.is/docs/juju/juju-deploy), constraints can be used to specify the juju machine resource requirements. For example, `juju deploy github-runner --constraints="cores=4 mem=16G disk=20G"`.
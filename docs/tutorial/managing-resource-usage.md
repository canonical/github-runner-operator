# Managing resource usage

The charm can be hardware intensive, as each instance of self-hosted runner application is hosted in a virtual machine.

## Virtual machine resource usage

The minimum requirements for a single virtual machine are:

- 1 [virtual machine vCPU](https://charmhub.io/github-runner/configure#vm-cpu)
- 2GiB of [virtual machine memory](https://charmhub.io/github-runner/configure#vm-memory)
- 10GiB of [virtual machine disk](https://charmhub.io/github-runner/configure#vm-disk)

## Juju machine resource usage

It is recommended the Juju machine has a minimum of 4GiB of memory dedicated to itself. Generally, 20GiB of disk is provisioned for the Juju machine for the Juju logs.

The Juju machine will also need the enough resources to host the virtual machines.

The recommended combined resource usage is:

- vCPU: Depends on the workload
- memory: number of virtual machines * (memory per virtual machine + disk per virtual machine) + 4GiB
- disk: 20GiB

If memory is used as [runner storage](https://charmhub.io/github-runner/docs/configure-runner-storage):

- memory: number of virtual machines * (memory per virtual machine + disk per virtual machine) + 4GiB

## Juju machine constraints

During [deployment of the charm](https://juju.is/docs/juju/juju-deploy), constraints can be used to specify the Juju machine resource requirements. For example, `juju deploy github-runner --constraints="cores=4 mem=16G disk=20G"`.

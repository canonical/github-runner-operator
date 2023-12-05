# ARM64

### Nested virtualiztion support

GitHub runner uses [LXD](https://github.com/canonical/lxd) to create a virtual machine to run the 
GitHub runner's binary. Some versions of the ARM64 architecture do not support nested 
virtualizations. 

Furthermore LXD by default uses QEMU with KVM acceleration options and such behavior cannot
overriden. When run on a machine without KVM support,
the following error will occur:
```
Error: Failed instance creation: Failed creating instance record: Instance type "virtual-machine"
is not supported on this server: KVM support is missing (no /dev/kvm)
```

The kernel for nested virtualizations have not yet landed upstream.

The current progress of ARM64 nested virtualization support requires a few underlying technologies
to be further developed.
- [Hardware: supported](https://developer.arm.com/documentation/102142/0100/Nested-virtualization)
- Kernel (KVM): upstream not yet ready
- Userspace programs (e.g. qemu): unsupported.

Therefore, it is currently necessary that the charm is deployed on a bare metal instance.

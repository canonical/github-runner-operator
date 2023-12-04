# ARM64

### Nested virtualiztion support

GitHub runner uses [LXD](https://github.com/canonical/lxd) to create a virtual machine to run the 
GitHub runner's binary. Some versions of the ARM64 architecture do not support nested 
virtualizations. 

Furthermore LXD uses QEMU with KVM acceleration options. When run on a nested virtual machine, 
the following error will occur:
```
Error: Failed instance creation: Failed creating instance record: Instance type "virtual-machine"
is not supported on this server: KVM support is missing (no /dev/kvm)
```

Therefore, it is necessary that the charm is deployed on a bare metal instance.

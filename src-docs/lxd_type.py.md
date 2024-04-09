<!-- markdownlint-disable -->

<a href="../src/lxd_type.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `lxd_type.py`
Types used by Lxd class. 

The details of the configuration of different types of devices can be found here: https://linuxcontainers.org/lxd/docs/latest/reference/devices/ 

For example, configuration for disk: https://linuxcontainers.org/lxd/docs/latest/reference/devices_disk/# 

The unit of storage and network limits can be found here: https://linuxcontainers.org/lxd/docs/latest/reference/instance_units/#instances-limit-units 



---

## <kbd>class</kbd> `LxdInstanceConfig`
Configuration for the LXD instance. 

See https://documentation.ubuntu.com/lxd/en/latest/howto/instances_create/ 



**Attributes:**
 
 - <b>`name`</b>:  Name of the instance. 
 - <b>`type`</b>:  Instance type, i.e. "container" or "virtual-machine". 
 - <b>`source`</b>:  Instance creation source configuration. 
 - <b>`ephemeral`</b>:  Whether the container should be deleted after a single run. 
 - <b>`profiles`</b>:  List of LXD profiles applied to the instance. 





---

## <kbd>class</kbd> `LxdInstanceConfigSource`
Configuration for source image in the LXD instance. 



**Attributes:**
 
 - <b>`type`</b>:  Type of source configuration, e.g. image, disk 
 - <b>`server`</b>:  The source server URL, e.g. https://cloud-images.ubuntu.com/releases 
 - <b>`protocol`</b>:  Protocol of the configuration, e.g. simplestreams 
 - <b>`alias`</b>:  Alias for configuration. 





---

## <kbd>class</kbd> `LxdNetwork`
LXD network information. 



**Attributes:**
 
 - <b>`name`</b>:  The name of LXD network. 
 - <b>`description`</b>:  LXD network descriptor. 
 - <b>`type`</b>:  Network type, i.e. "bridge", "physical" 
 - <b>`config`</b>:  The LXD network configuration values. 
 - <b>`managed`</b>:  Whether the network is being managed by lxd. 
 - <b>`used_by`</b>:  Number of instances using the network. 





---

## <kbd>class</kbd> `LxdNetworkConfig`
Represent LXD network configuration. 





---

## <kbd>class</kbd> `LxdResourceProfileConfig`
Configuration LXD profile. 





---

## <kbd>class</kbd> `LxdResourceProfileDevicesDisk`
LXD device profile of disk. 





---

## <kbd>class</kbd> `LxdStoragePoolConfig`
Configuration of the storage pool. 



**Attributes:**
 
 - <b>`source`</b>:  The storage pool configuration source image. 
 - <b>`size`</b>:  The size of the storage pool, e.g. 30GiB 





---

## <kbd>class</kbd> `LxdStoragePoolConfiguration`
Configuration for LXD storage pool. 



**Attributes:**
 
 - <b>`name`</b>:  The storage pool name. 
 - <b>`driver`</b>:  The storage driver being used, i.e. "dir", "btrfs", ... . See             https://documentation.ubuntu.com/lxd/en/stable-5.0/reference/storage_drivers/             for more information. 
 - <b>`config`</b>:  The storage pool configuration. 






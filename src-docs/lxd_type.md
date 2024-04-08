<!-- markdownlint-disable -->

<a href="../src/lxd_cloud/lxd_type.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `lxd_type`
Types used by Lxd class. 

The details of the configuration of different types of devices can be found here: https://linuxcontainers.org/lxd/docs/latest/reference/devices/ 

For example, configuration for disk: https://linuxcontainers.org/lxd/docs/latest/reference/devices_disk/# 

The unit of storage and network limits can be found here: https://linuxcontainers.org/lxd/docs/latest/reference/instance_units/#instances-limit-units 



---

<a href="../src/lxd_cloud/lxd_type.py"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `LxdNetworkConfig`
Represent LXD network configuration. 





---

<a href="../src/lxd_cloud/lxd_type.py"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `LxdResourceProfileConfig`
Configuration LXD profile. 





---

<a href="../src/lxd_cloud/lxd_type.py"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `LxdResourceProfileDevicesDisk`
LXD device profile of disk. 





---

<a href="../src/lxd_cloud/lxd_type.py#L37"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `LxdInstanceConfigSource`
Configuration for source image in the LXD instance. 





---

<a href="../src/lxd_cloud/lxd_type.py#L47"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `LxdInstanceConfig`
Configuration for the LXD instance. 





---

<a href="../src/lxd_cloud/lxd_type.py#L65"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `LxdStoragePoolConfig`
Configuration of the storage pool. 





---

<a href="../src/lxd_cloud/lxd_type.py#L72"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `LxdStoragePoolConfiguration`
Configuration for LXD storage pool. 





---

<a href="../src/lxd_cloud/lxd_type.py#L80"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `LxdNetwork`
LXD network information. 

<a href="../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    name: str,
    description: str,
    type: str,
    config: LxdNetworkConfig,
    managed: bool,
    used_by: tuple[str]
) → None
```










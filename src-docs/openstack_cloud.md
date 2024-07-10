<!-- markdownlint-disable -->

<a href="../src/openstack_cloud/__init__.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `openstack_cloud`
Module for managing Openstack cloud. 

**Global Variables**
---------------
- **openstack_manager**: # Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.


---

<a href="../src/openstack_cloud/__init__.py#L110"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `initialize`

```python
initialize(cloud_config: dict) → None
```

Initialize Openstack integration. 

Validates config and writes it to disk. 



**Raises:**
 
 - <b>`OpenStackInvalidConfigError`</b>:  If there was an given cloud config. 



**Args:**
 
 - <b>`cloud_config`</b>:  The configuration in clouds.yaml format to apply. 


---

<a href="../src/openstack_cloud/__init__.py#L68"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `CloudConfig`
The parsed clouds.yaml configuration dictionary. 



**Attributes:**
 
 - <b>`clouds`</b>:  A mapping of key "clouds" to cloud name mapped to cloud configuration. 






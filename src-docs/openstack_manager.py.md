<!-- markdownlint-disable -->

<a href="../src/openstack_manager.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `openstack_manager.py`
Module for handling interactions with OpenStack. 


---

<a href="../src/openstack_manager.py#L77"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `initialize`

```python
initialize(cloud_config: dict) → None
```

Initialize Openstack integration. 

Validates config and writes it to disk. 



**Args:**
 
 - <b>`cloud_config`</b>:  The configuration in clouds.yaml format to apply. 



**Raises:**
 
 - <b>`InvalidConfigError`</b>:  if the format of the config is invalid. 


---

<a href="../src/openstack_manager.py#L92"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `list_projects`

```python
list_projects(cloud_config: dict) → list[Project]
```

List all projects in the OpenStack cloud. 

The purpose of the method is just to try out openstack integration and it may be removed in the future. 

It currently returns objects directly from the sdk, which may not be ideal (mapping to domain objects may be preferable). 



**Returns:**
  A list of projects. 



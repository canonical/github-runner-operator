<!-- markdownlint-disable -->

<a href="../src/openstack_manager.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `openstack_manager.py`
Module for handling interactions with OpenStack. 


---

<a href="../src/openstack_manager.py#L33"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `initialize_openstack`

```python
initialize_openstack(clouds_yaml: str) → None
```

Initialize clouds.yaml and check connection. 



**Args:**
 
 - <b>`clouds_yaml`</b>:  The clouds.yaml configuration to apply. 



**Raises:**
 
 - <b>`InvalidConfigError`</b>:  if an invalid clouds_yaml configuration was passed. 


---

## <kbd>class</kbd> `InvalidConfigError`
Represents an invalid OpenStack configuration. 



**Attributes:**
 
 - <b>`msg`</b>:  Explanation of the error. 

<a href="../src/openstack_manager.py#L24"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str)
```

Initialize a new instance of the InvalidConfigError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 






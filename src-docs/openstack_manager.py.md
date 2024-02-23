<!-- markdownlint-disable -->

<a href="../src/openstack_manager.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `openstack_manager.py`
Module for handling interactions with OpenStack. 

**Global Variables**
---------------
- **IMAGE_NAME**
- **BUILD_OPENSTACK_IMAGE_SCRIPT_FILENAME**

---

<a href="../src/openstack_manager.py#L86"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/openstack_manager.py#L101"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `list_projects`

```python
list_projects(cloud_config: dict) → list[Project]
```

List all projects in the OpenStack cloud. 

The purpose of the method is just to try out openstack integration and it may be removed in the future. 

It currently returns objects directly from the sdk, which may not be ideal (mapping to domain objects may be preferable). 



**Returns:**
  A list of projects. 


---

<a href="../src/openstack_manager.py#L155"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `build_image`

```python
build_image(cloud_config: dict, proxies: Optional[ProxySetting] = None) → Image
```

Build and upload an image to OpenStack. 



**Args:**
 
 - <b>`cloud_config`</b>:  The cloud configuration to connect OpenStack with. 
 - <b>`proxies`</b>:  HTTP proxy settings. 



**Raises:**
 
 - <b>`ImageBuildError`</b>:  If there were errors buliding/creating the image. 



**Returns:**
 The OpenStack image object. 


---

## <kbd>class</kbd> `ImageBuildError`
Exception representing an error during image build process. 






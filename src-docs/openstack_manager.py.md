<!-- markdownlint-disable -->

<a href="../src/openstack_manager.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `openstack_manager.py`
Module for handling interactions with OpenStack. 

**Global Variables**
---------------
- **IMAGE_NAME**
- **BUILD_OPENSTACK_IMAGE_SCRIPT_FILENAME**

---

<a href="../src/openstack_manager.py#L90"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/openstack_manager.py#L105"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/openstack_manager.py#L181"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `build_image`

```python
build_image(
    cloud_config: dict,
    runner_info: RunnerApplication,
    proxies: Optional[ProxySetting] = None
) → Image
```

Build and upload an image to OpenStack. 



**Args:**
 
 - <b>`cloud_config`</b>:  The cloud configuration to connect OpenStack with. 
 - <b>`runner_info`</b>:  The runner application metadata. 
 - <b>`proxies`</b>:  HTTP proxy settings. 



**Raises:**
 
 - <b>`ImageBuildError`</b>:  If there were errors buliding/creating the image. 



**Returns:**
 The OpenStack image object. 


---

<a href="../src/openstack_manager.py#L215"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `create_instance`

```python
create_instance(cloud_config: dict, instance_config: InstanceConfig) → Server
```

Create an OpenStack instance. 



**Args:**
 
 - <b>`cloud_config`</b>:  The cloud configuration to connect Openstack with. 
 - <b>`instance_config`</b>:  The configuration values for Openstack instance to launch. 



**Raises:**
 
 - <b>`InstanceLaunchError`</b>:  if any errors occurred while launching Openstack instance. 



**Returns:**
 The created server. 


---

## <kbd>class</kbd> `ImageBuildError`
Exception representing an error during image build process. 





---

## <kbd>class</kbd> `InstanceConfig`
The configuration values for creating a single runner instance. 



**Args:**
 
 - <b>`name`</b>:  Name of the image to launch the GitHub runner instance with. 
 - <b>`labels`</b>:  The runner instance labels. 
 - <b>`registration_token`</b>:  Token for registering the runner on GitHub. 
 - <b>`github_path`</b>:  The GitHub repo/org path 
 - <b>`image`</b>:  The Openstack image to use to boot the instance with. 





---

## <kbd>class</kbd> `InstanceLaunchError`
Exception representing an error during instance launch process. 






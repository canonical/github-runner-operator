<!-- markdownlint-disable -->

<a href="../src/openstack_manager.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `openstack_manager.py`
Module for handling interactions with OpenStack. 

**Global Variables**
---------------
- **IMAGE_PATH_TMPL**
- **IMAGE_NAME**
- **BUILD_OPENSTACK_IMAGE_SCRIPT_FILENAME**

---

<a href="../src/openstack_manager.py#L63"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `list_projects`

```python
list_projects(cloud_config: dict[str, dict]) → list[Project]
```

List all projects in the OpenStack cloud. 

The purpose of the method is just to try out openstack integration and it may be removed in the future. 

It currently returns objects directly from the sdk, which may not be ideal (mapping to domain objects may be preferable). 



**Returns:**
  A list of projects. 


---

<a href="../src/openstack_manager.py#L134"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `build_image`

```python
build_image(
    arch: Arch,
    cloud_config: dict[str, dict],
    github_client: GithubClient,
    path: GithubOrg | GithubRepo,
    proxies: Optional[ProxyConfig] = None
) → Image
```

Build and upload an image to OpenStack. 



**Args:**
 
 - <b>`cloud_config`</b>:  The cloud configuration to connect OpenStack with. 
 - <b>`github_client`</b>:  The Github client to interact with Github API. 
 - <b>`path`</b>:  Github organisation or repository path. 
 - <b>`proxies`</b>:  HTTP proxy settings. 



**Raises:**
 
 - <b>`ImageBuildError`</b>:  If there were errors building/creating the image. 



**Returns:**
 The OpenStack image object. 


---

<a href="../src/openstack_manager.py#L181"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `create_instance_config`

```python
create_instance_config(
    unit_name: str,
    openstack_image: Image,
    path: GithubOrg | GithubRepo,
    github_client: GithubClient
) → InstanceConfig
```

Create an instance config from charm data. 



**Args:**
 
 - <b>`unit_name`</b>:  The charm unit name. 
 - <b>`image`</b>:  Ubuntu image flavor. 
 - <b>`path`</b>:  Github organisation or repository path. 
 - <b>`github_client`</b>:  The Github client to interact with Github API. 


---

<a href="../src/openstack_manager.py#L211"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `create_instance`

```python
create_instance(
    cloud_config: dict[str, dict],
    instance_config: InstanceConfig
) → Server
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
 - <b>`openstack_image`</b>:  The Openstack image to use to boot the instance with. 





---

## <kbd>class</kbd> `InstanceLaunchError`
Exception representing an error during instance launch process. 






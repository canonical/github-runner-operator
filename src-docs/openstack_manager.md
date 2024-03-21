<!-- markdownlint-disable -->

<a href="../src/openstack_cloud/openstack_manager.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `openstack_manager`
Module for handling interactions with OpenStack. 

**Global Variables**
---------------
- **IMAGE_PATH_TMPL**
- **IMAGE_NAME**
- **BUILD_OPENSTACK_IMAGE_SCRIPT_FILENAME**

---

<<<<<<< HEAD
<a href="../src/openstack_cloud/openstack_manager.py#L63"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `list_projects`

```python
list_projects(cloud_config: dict[str, dict]) → list[Project]
```

List all projects in the OpenStack cloud. 

The purpose of the method is just to try out openstack integration and it may be removed in the future. 

It currently returns objects directly from the sdk, which may not be ideal (mapping to domain objects may be preferable). 



**Args:**
 
 - <b>`cloud_config`</b>:  The dict mapping of cloud name to connection configuration. 



**Raises:**
 
 - <b>`OpenStackUnauthorizedError`</b>:  If there was an authorization error with given cloud config. 



**Returns:**
 A list of projects. 


---

<a href="../src/openstack_cloud/openstack_manager.py#L184"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>
=======
<a href="../src/openstack_cloud/openstack_manager.py#L232"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>
>>>>>>> c57beb0daae5a7c242a7eb89409db8b6d815029b

## <kbd>function</kbd> `build_image`

```python
build_image(
    arch: Arch,
    cloud_config: dict[str, dict],
    github_client: GithubClient,
    path: GithubOrg | GithubRepo,
    proxies: Optional[ProxyConfig] = None
) → str
```

Build and upload an image to OpenStack. 



**Args:**
 
<<<<<<< HEAD
 - <b>`arch`</b>:  The system architecture to build the image for. 
=======
>>>>>>> c57beb0daae5a7c242a7eb89409db8b6d815029b
 - <b>`cloud_config`</b>:  The cloud configuration to connect OpenStack with. 
 - <b>`github_client`</b>:  The Github client to interact with Github API. 
 - <b>`path`</b>:  Github organisation or repository path. 
 - <b>`proxies`</b>:  HTTP proxy settings. 



**Raises:**
 
<<<<<<< HEAD
 - <b>`OpenstackImageBuildError`</b>:  If there were errors building/creating the image. 
=======
 - <b>`ImageBuildError`</b>:  If there were errors building/creating the image. 
>>>>>>> c57beb0daae5a7c242a7eb89409db8b6d815029b



**Returns:**
 The created OpenStack image id. 


---

<<<<<<< HEAD
<a href="../src/openstack_cloud/openstack_manager.py#L238"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>
=======
<a href="../src/openstack_cloud/openstack_manager.py#L289"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>
>>>>>>> c57beb0daae5a7c242a7eb89409db8b6d815029b

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
<<<<<<< HEAD
 - <b>`openstack_image`</b>:  The openstack image object to create the instance with. 
=======
 - <b>`image`</b>:  Ubuntu image flavor. 
>>>>>>> c57beb0daae5a7c242a7eb89409db8b6d815029b
 - <b>`path`</b>:  Github organisation or repository path. 
 - <b>`github_client`</b>:  The Github client to interact with Github API. 


<<<<<<< HEAD

**Returns:**
 Instance configuration created. 


---

<a href="../src/utilities.py#L318"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>
=======
---

<a href="../src/utilities.py#L362"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>
>>>>>>> c57beb0daae5a7c242a7eb89409db8b6d815029b

## <kbd>function</kbd> `create_instance`

```python
create_instance(
    cloud_config: dict[str, dict],
    instance_config: InstanceConfig,
    proxies: Optional[ProxyConfig] = None,
    dockerhub_mirror: Optional[str] = None,
    ssh_debug_connections: list[SSHDebugConnection] | None = None
) → None
```

Create an OpenStack instance. 



**Args:**
 
 - <b>`cloud_config`</b>:  The cloud configuration to connect Openstack with. 
 - <b>`instance_config`</b>:  The configuration values for Openstack instance to launch. 
<<<<<<< HEAD
 - <b>`proxies`</b>:  HTTP proxy settings. dockerhub_mirror: ssh_debug_connections: 
=======
>>>>>>> c57beb0daae5a7c242a7eb89409db8b6d815029b



**Raises:**
 
<<<<<<< HEAD
 - <b>`InstanceLaunchError`</b>:  if any errors occurred while launching Openstack instance. 
=======
 - <b>`OpenstackInstanceLaunchError`</b>:  if any errors occurred while launching Openstack instance. 
>>>>>>> c57beb0daae5a7c242a7eb89409db8b6d815029b


---

<<<<<<< HEAD
<a href="../src/openstack_cloud/openstack_manager.py#L144"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>
=======
<a href="../src/openstack_cloud/openstack_manager.py#L75"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `ProxyStringValues`
Wrapper class to proxy values to string. 



**Attributes:**
 
 - <b>`http`</b>:  HTTP proxy address. 
 - <b>`https`</b>:  HTTPS proxy address. 
 - <b>`no_proxy`</b>:  Comma-separated list of hosts that should not be proxied. 





---

<a href="../src/openstack_cloud/openstack_manager.py#L186"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>
>>>>>>> c57beb0daae5a7c242a7eb89409db8b6d815029b

## <kbd>class</kbd> `InstanceConfig`
The configuration values for creating a single runner instance. 



<<<<<<< HEAD
**Attributes:**
=======
**Args:**
>>>>>>> c57beb0daae5a7c242a7eb89409db8b6d815029b
 
 - <b>`name`</b>:  Name of the image to launch the GitHub runner instance with. 
 - <b>`labels`</b>:  The runner instance labels. 
 - <b>`registration_token`</b>:  Token for registering the runner on GitHub. 
 - <b>`github_path`</b>:  The GitHub repo/org path 
 - <b>`openstack_image`</b>:  The Openstack image to use to boot the instance with. 

<a href="../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    name: str,
    labels: Iterable[str],
    registration_token: str,
    github_path: GithubOrg | GithubRepo,
    openstack_image: Image
) → None
```









<<<<<<< HEAD
---

<a href="../src/openstack_cloud/openstack_manager.py#L267"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `InstanceLaunchError`
Exception representing an error during instance launch process. 





=======
>>>>>>> c57beb0daae5a7c242a7eb89409db8b6d815029b

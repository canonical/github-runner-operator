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

<a href="../src/openstack_cloud/openstack_manager.py#L299"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `build_image`

```python
build_image(
    cloud_config: dict[str, dict],
    github_client: GithubClient,
    path: GithubOrg | GithubRepo,
    config: BuildImageConfig
) → str
```

Build and upload an image to OpenStack. 



**Args:**
 
 - <b>`arch`</b>:  The system architecture to build the image for. 
 - <b>`cloud_config`</b>:  The cloud configuration to connect OpenStack with. 
 - <b>`github_client`</b>:  The Github client to interact with Github API. 
 - <b>`path`</b>:  Github organisation or repository path. 
 - <b>`config`</b>:  The image build configuration values. 



**Raises:**
 
 - <b>`OpenstackImageBuildError`</b>:  If there were errors building/creating the image. 



**Returns:**
 The created OpenStack image id. 


---

<a href="../src/openstack_cloud/openstack_manager.py#L345"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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
 - <b>`openstack_image`</b>:  The openstack image object to create the instance with. 
 - <b>`path`</b>:  Github organisation or repository path. 
 - <b>`github_client`</b>:  The Github client to interact with Github API. 



**Returns:**
 Instance configuration created. 


---

<a href="../src/utilities.py#L421"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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
 - <b>`proxies`</b>:  HTTP proxy settings. dockerhub_mirror: ssh_debug_connections: 



**Raises:**
 
 - <b>`OpenstackInstanceLaunchError`</b>:  if any errors occurred while launching Openstack instance. 


---

<a href="../src/openstack_cloud/openstack_manager.py#L81"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `ProxyStringValues`
Wrapper class to proxy values to string. 



**Attributes:**
 
 - <b>`http`</b>:  HTTP proxy address. 
 - <b>`https`</b>:  HTTPS proxy address. 
 - <b>`no_proxy`</b>:  Comma-separated list of hosts that should not be proxied. 





---

<a href="../src/openstack_cloud/openstack_manager.py#L198"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `InstanceConfig`
The configuration values for creating a single runner instance. 



**Attributes:**
 
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









---

<a href="../src/openstack_cloud/openstack_manager.py#L247"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `BuildImageConfig`
The configuration values for building openstack image. 



**Attributes:**
 
 - <b>`arch`</b>:  The image architecture to build for. 
 - <b>`base_image`</b>:  The ubuntu image to use as image build base. 
 - <b>`proxies`</b>:  HTTP proxy settings. 

<a href="../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    arch: Arch,
    base_image: BaseImage,
    proxies: Optional[ProxyConfig] = None
) → None
```









---

<a href="../src/openstack_cloud/openstack_manager.py#L262"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `ImageDeleteError`
Represents an error while deleting existing openstack image. 






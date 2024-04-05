<!-- markdownlint-disable -->

<a href="../src/openstack_cloud/openstack_manager.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `openstack_manager`
Module for handling interactions with OpenStack. 

**Global Variables**
---------------
- **IMAGE_PATH_TMPL**
- **IMAGE_NAME**
- **SECURITY_GROUP_NAME**
- **BUILD_OPENSTACK_IMAGE_SCRIPT_FILENAME**

---

<a href="../src/openstack_cloud/openstack_manager.py#L269"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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
 
 - <b>`cloud_config`</b>:  The cloud configuration to connect OpenStack with. 
 - <b>`github_client`</b>:  The Github client to interact with Github API. 
 - <b>`path`</b>:  Github organisation or repository path. 
 - <b>`proxies`</b>:  HTTP proxy settings. 



**Raises:**
 
 - <b>`ImageBuildError`</b>:  If there were errors building/creating the image. 



**Returns:**
 The created OpenStack image id. 


---

<a href="../src/openstack_cloud/openstack_manager.py#L337"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `create_instance_config`

```python
create_instance_config(
    app_name: str,
    unit_num: int,
    openstack_image: str,
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

<a href="../src/utilities.py#L410"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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



**Raises:**
 
 - <b>`OpenstackInstanceLaunchError`</b>:  if any errors occurred while launching Openstack instance. 


---

<a href="../src/openstack_cloud/openstack_manager.py#L89"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `ProxyStringValues`
Wrapper class to proxy values to string. 



**Attributes:**
 
 - <b>`http`</b>:  HTTP proxy address. 
 - <b>`https`</b>:  HTTPS proxy address. 
 - <b>`no_proxy`</b>:  Comma-separated list of hosts that should not be proxied. 





---

<a href="../src/openstack_cloud/openstack_manager.py#L200"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `InstanceConfig`
The configuration values for creating a single runner instance. 



**Args:**
 
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
    openstack_image: str
) → None
```









---

<a href="../src/openstack_cloud/openstack_manager.py#L452"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `GithubRunnerRemoveError`
Represents an error removing registered runner from Github. 





---

<a href="../src/openstack_cloud/openstack_manager.py#L460"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `OpenstackRunnerManager`
Runner manager for OpenStack-based instances. 



**Attributes:**
 
 - <b>`app_name`</b>:  An name for the set of runners. 
 - <b>`unit`</b>:  Unit number of the set of runners. 
 - <b>`instance_name`</b>:  Prefix of the name for the set of runners. 
 - <b>`flavor`</b>:  OpenStack flavor for defining the runner resources. 
 - <b>`network`</b>:  OpenStack network for runner network access. 

<a href="../src/openstack_cloud/openstack_manager.py#L471"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    app_name: str,
    unit_num: int,
    openstack_runner_manager_config: OpenstackRunnerManagerConfig,
    cloud_config: dict[str, dict]
)
```

Construct OpenstackRunnerManager object. 



**Args:**
 
 - <b>`app_name`</b>:  An name for the set of runners. 
 - <b>`unit`</b>:  Unit number of the set of runners. 
 - <b>`openstack_runner_manager_config`</b>:  Configurations related to runner manager. 
 - <b>`cloud_config`</b>:  The openstack clouds.yaml in dict format. 




---

<a href="../src/openstack_cloud/openstack_manager.py#L859"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `flush`

```python
flush() → int
```

Flush Openstack servers. 

---

<a href="../src/openstack_cloud/openstack_manager.py#L687"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_github_runner_info`

```python
get_github_runner_info() → tuple[RunnerGithubInfo]
```

Get information on GitHub for the runners. 



**Returns:**
  Collection of runner GitHub information. 

---

<a href="../src/openstack_cloud/openstack_manager.py#L820"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `reconcile`

```python
reconcile(quantity: int) → int
```

Reconcile the quantity of runners. 



**Args:**
 
 - <b>`quantity`</b>:  The number of intended runners. 



**Returns:**
 The change in number of runners. 



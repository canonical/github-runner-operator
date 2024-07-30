<!-- markdownlint-disable -->

<a href="../src/openstack_cloud/openstack_manager.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `openstack_cloud.openstack_manager`
Module for handling interactions with OpenStack. 

**Global Variables**
---------------
- **RUNNER_INSTALLED_TS_FILE_NAME**
- **SECURITY_GROUP_NAME**
- **BUILD_OPENSTACK_IMAGE_SCRIPT_FILENAME**
- **MAX_METRICS_FILE_SIZE**
- **RUNNER_STARTUP_PROCESS**
- **RUNNER_LISTENER_PROCESS**
- **RUNNER_WORKER_PROCESS**
- **CREATE_SERVER_TIMEOUT**

---

<a href="../src/openstack_cloud/openstack_manager.py#L153"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `create_instance_config`

```python
create_instance_config(
    app_name: str,
    unit_num: int,
    image_id: str,
    path: GithubOrg | GithubRepo,
    labels: Iterable[str],
    registration_token: str
) → InstanceConfig
```

Create an instance config from charm data. 



**Args:**
 
 - <b>`app_name`</b>:  The juju application name. 
 - <b>`unit_num`</b>:  The juju unit number. 
 - <b>`image_id`</b>:  The openstack image id to create the instance with. 
 - <b>`path`</b>:  Github organisation or repository path. 
 - <b>`labels`</b>:  Addition labels for the runner. 
 - <b>`registration_token`</b>:  The Github runner registration token. See             https://docs.github.com/en/rest/actions/self-hosted-runners?apiVersion=2022-11-28#create-a-registration-token-for-a-repository 



**Returns:**
 Instance configuration created. 


---

<a href="../src/openstack_cloud/openstack_manager.py#L111"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `InstanceConfig`
The configuration values for creating a single runner instance. 



**Attributes:**
 
 - <b>`github_path`</b>:  The GitHub repo/org path to register the runner. 
 - <b>`image_id`</b>:  The Openstack image id to use to boot the instance with. 
 - <b>`labels`</b>:  The runner instance labels. 
 - <b>`name`</b>:  Name of the image to launch the GitHub runner instance with. 
 - <b>`registration_token`</b>:  Token for registering the runner on GitHub. 

<a href="../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    github_path: GithubOrg | GithubRepo,
    image_id: str,
    labels: Iterable[str],
    name: str,
    registration_token: str
) → None
```









---

<a href="../src/openstack_cloud/openstack_manager.py#L246"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `GithubRunnerRemoveError`
Represents an error removing registered runner from Github. 





---

<a href="../src/openstack_cloud/openstack_manager.py#L256"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `OpenstackRunnerManager`
Runner manager for OpenStack-based instances. 



**Attributes:**
 
 - <b>`app_name`</b>:  The juju application name. 
 - <b>`unit_num`</b>:  The juju unit number. 
 - <b>`instance_name`</b>:  Prefix of the name for the set of runners. 

<a href="../src/openstack_cloud/openstack_manager.py#L265"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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
 
 - <b>`app_name`</b>:  The juju application name. 
 - <b>`unit_num`</b>:  The juju unit number. 
 - <b>`openstack_runner_manager_config`</b>:  Configurations related to runner manager. 
 - <b>`cloud_config`</b>:  The openstack clouds.yaml in dict format. 




---

<a href="../src/openstack_cloud/openstack_manager.py#L1478"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `flush`

```python
flush() → int
```

Flush Openstack servers. 



**Returns:**
  The number of runners flushed. 

---

<a href="../src/openstack_cloud/openstack_manager.py#L367"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_github_runner_info`

```python
get_github_runner_info() → tuple[RunnerGithubInfo, ]
```

Get information on GitHub for the runners. 



**Returns:**
  Collection of runner GitHub information. 

---

<a href="../src/openstack_cloud/openstack_manager.py#L296"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `reconcile`

```python
reconcile(quantity: int) → int
```

Reconcile the quantity of runners. 



**Args:**
 
 - <b>`quantity`</b>:  The number of intended runners. 



**Returns:**
 The change in number of runners. 



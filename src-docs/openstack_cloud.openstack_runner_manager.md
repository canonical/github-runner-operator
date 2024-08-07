<!-- markdownlint-disable -->

<a href="../src/openstack_cloud/openstack_runner_manager.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `openstack_cloud.openstack_runner_manager`
Manager for self-hosted runner on OpenStack. 

**Global Variables**
---------------
- **BUILD_OPENSTACK_IMAGE_SCRIPT_FILENAME**
- **MAX_METRICS_FILE_SIZE**
- **RUNNER_STARTUP_PROCESS**
- **RUNNER_LISTENER_PROCESS**
- **RUNNER_WORKER_PROCESS**
- **CREATE_SERVER_TIMEOUT**


---

<a href="../src/openstack_cloud/openstack_runner_manager.py#L66"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `OpenstackRunnerManagerConfig`
Configuration for OpenstackRunnerManager. 

<a href="../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    clouds_config: dict[str, dict],
    cloud: str,
    image: str,
    flavor: str,
    network: str,
    github_path: GithubOrg | GithubRepo,
    labels: list[str],
    proxy_config: ProxyConfig | None,
    dockerhub_mirror: str | None,
    ssh_debug_connections: list[SSHDebugConnection] | None,
    repo_policy_url: str | None,
    repo_policy_token: str | None
) → None
```









---

<a href="../src/openstack_cloud/openstack_runner_manager.py#L84"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `OpenstackRunnerManager`
Manage self-hosted runner on OpenStack cloud. 

<a href="../src/openstack_cloud/openstack_runner_manager.py#L87"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(prefix: str, config: OpenstackRunnerManagerConfig) → None
```

Construct the object. 



**Args:**
 
 - <b>`prefix`</b>:  The prefix to runner name. 
 - <b>`config`</b>:  Configuration of the object. 




---

<a href="../src/openstack_cloud/openstack_runner_manager.py#L233"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `cleanup`

```python
cleanup(remove_token: str) → None
```

Cleanup runner and resource on the cloud. 



**Args:**
 
 - <b>`remove_token`</b>:  The GitHub remove token. 

---

<a href="../src/openstack_cloud/openstack_runner_manager.py#L110"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `create_runner`

```python
create_runner(registration_token: str) → str
```

Create a self-hosted runner. 



**Args:**
 
 - <b>`registration_token`</b>:  The GitHub registration token for registering runners. 



**Returns:**
 Instance ID of the runner. 

---

<a href="../src/openstack_cloud/openstack_runner_manager.py#L192"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `delete_runner`

```python
delete_runner(id: str, remove_token: str) → None
```

Delete self-hosted runners. 



**Args:**
 
 - <b>`id`</b>:  The instance id of the runner to delete. 
 - <b>`remove_token`</b>:  The GitHub remove token. 

---

<a href="../src/openstack_cloud/openstack_runner_manager.py#L102"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_name_prefix`

```python
get_name_prefix() → str
```

Get the name prefix of the self-hosted runners. 



**Returns:**
  The name prefix. 

---

<a href="../src/openstack_cloud/openstack_runner_manager.py#L147"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_runner`

```python
get_runner(id: str) → CloudRunnerInstance | None
```

Get a self-hosted runner by instance id. 



**Args:**
 
 - <b>`id`</b>:  The instance id. 



**Returns:**
 Information on the runner instance. 

---

<a href="../src/openstack_cloud/openstack_runner_manager.py#L167"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_runners`

```python
get_runners(
    states: Optional[Sequence[CloudRunnerState]] = None
) → Tuple[CloudRunnerInstance]
```

Get self-hosted runners by state. 



**Args:**
 
 - <b>`states`</b>:  Filter for the runners with these github states. If None all states will be  included. 



**Returns:**
 Information on the runner instances. 



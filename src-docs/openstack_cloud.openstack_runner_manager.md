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

<a href="../src/openstack_cloud/openstack_runner_manager.py#L64"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `OpenstackRunnerManagerConfig`
Configuration for OpenstackRunnerManager. 



**Attributes:**
 
 - <b>`clouds_config`</b>:  The clouds.yaml. 
 - <b>`cloud`</b>:  The cloud name to connect to. 
 - <b>`image`</b>:  The image name for runners to use. 
 - <b>`flavor`</b>:  The flavor name for runners to use. 
 - <b>`network`</b>:  The network name for runners to use. 
 - <b>`github_path`</b>:  The GitHub organization or repository for runners to connect to. 
 - <b>`labels`</b>:  The labels to add to runners. 
 - <b>`proxy_config`</b>:  The proxy configuration. 
 - <b>`dockerhub_mirror`</b>:  The dockerhub mirror to use for runners. 
 - <b>`ssh_debug_connections`</b>:  The information on the ssh debug services. 
 - <b>`repo_policy_url`</b>:  The URL of the repo policy service. 
 - <b>`repo_policy_token`</b>:  The token to access the repo policy service. 

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

<a href="../src/openstack_cloud/openstack_runner_manager.py#L97"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerHealth`
Runners with health state. 



**Attributes:**
 
 - <b>`healthy`</b>:  The list of healthy runners. 
 - <b>`unhealthy`</b>:   The list of unhealthy runners. 

<a href="../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    healthy: tuple[OpenstackInstance],
    unhealthy: tuple[OpenstackInstance]
) → None
```









---

<a href="../src/openstack_cloud/openstack_runner_manager.py#L110"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `OpenstackRunnerManager`
Manage self-hosted runner on OpenStack cloud. 

<a href="../src/openstack_cloud/openstack_runner_manager.py#L113"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(prefix: str, config: OpenstackRunnerManagerConfig) → None
```

Construct the object. 



**Args:**
 
 - <b>`prefix`</b>:  The prefix to runner name. 
 - <b>`config`</b>:  Configuration of the object. 




---

<a href="../src/openstack_cloud/openstack_runner_manager.py#L237"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `cleanup`

```python
cleanup(remove_token: str) → Iterator[RunnerMetrics]
```

Cleanup runner and resource on the cloud. 



**Args:**
 
 - <b>`remove_token`</b>:  The GitHub remove token. 



**Returns:**
 Any metrics retrieved from cleanup runners. 

---

<a href="../src/openstack_cloud/openstack_runner_manager.py#L136"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `create_runner`

```python
create_runner(registration_token: str) → str
```

Create a self-hosted runner. 



**Args:**
 
 - <b>`registration_token`</b>:  The GitHub registration token for registering runners. 



**Raises:**
 
 - <b>`RunnerCreateError`</b>:  Unable to create runner due to OpenStack issues. 



**Returns:**
 Instance ID of the runner. 

---

<a href="../src/openstack_cloud/openstack_runner_manager.py#L221"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `delete_runner`

```python
delete_runner(id: str, remove_token: str) → RunnerMetrics | None
```

Delete self-hosted runners. 



**Args:**
 
 - <b>`id`</b>:  The instance id of the runner to delete. 
 - <b>`remove_token`</b>:  The GitHub remove token. 

---

<a href="../src/openstack_cloud/openstack_runner_manager.py#L128"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_name_prefix`

```python
get_name_prefix() → str
```

Get the name prefix of the self-hosted runners. 



**Returns:**
  The name prefix. 

---

<a href="../src/openstack_cloud/openstack_runner_manager.py#L176"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/openstack_cloud/openstack_runner_manager.py#L196"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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



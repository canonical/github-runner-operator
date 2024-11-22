<!-- markdownlint-disable -->

<a href="../../github-runner-manager/src/github_runner_manager/openstack_cloud/openstack_runner_manager.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `openstack_cloud.openstack_runner_manager`
Manager for self-hosted runner on OpenStack. 

**Global Variables**
---------------
- **CREATE_SERVER_TIMEOUT**
- **RUNNER_LISTENER_PROCESS**
- **RUNNER_WORKER_PROCESS**
- **BUILD_OPENSTACK_IMAGE_SCRIPT_FILENAME**
- **MAX_METRICS_FILE_SIZE**
- **RUNNER_STARTUP_PROCESS**
- **OUTDATED_METRICS_STORAGE_IN_SECONDS**


---

<a href="../../github-runner-manager/src/github_runner_manager/openstack_cloud/openstack_runner_manager.py#L82"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `OpenStackServerConfig`
Configuration for OpenStack server. 



**Attributes:**
 
 - <b>`image`</b>:  The image name for runners to use. 
 - <b>`flavor`</b>:  The flavor name for runners to use. 
 - <b>`network`</b>:  The network name for runners to use. 

<a href="../../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(image: str, flavor: str, network: str) → None
```









---

<a href="../../github-runner-manager/src/github_runner_manager/openstack_cloud/openstack_runner_manager.py#L97"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `OpenStackRunnerManagerConfig`
Configuration for OpenStack runner manager. 



**Attributes:**
 
 - <b>`name`</b>:  The name of the manager. 
 - <b>`prefix`</b>:  The prefix of the runner names. 
 - <b>`credentials`</b>:  The OpenStack authorization information. 
 - <b>`server_config`</b>:  The configuration for OpenStack server. 
 - <b>`runner_config`</b>:  The configuration for the GitHub runner. 
 - <b>`service_config`</b>:  The configuration for supporting services. 
 - <b>`system_user_config`</b>:  The user to use for creating metrics storage. 

<a href="../../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    name: str,
    prefix: str,
    credentials: OpenStackCredentials,
    server_config: OpenStackServerConfig | None,
    runner_config: GitHubRunnerConfig,
    service_config: SupportServiceConfig,
    system_user_config: SystemUserConfig
) → None
```









---

<a href="../../github-runner-manager/src/github_runner_manager/openstack_cloud/openstack_runner_manager.py#L133"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `OpenStackRunnerManager`
Manage self-hosted runner on OpenStack cloud. 



**Attributes:**
 
 - <b>`name_prefix`</b>:  The name prefix of the runners created. 

<a href="../../github-runner-manager/src/github_runner_manager/openstack_cloud/openstack_runner_manager.py#L140"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(config: OpenStackRunnerManagerConfig) → None
```

Construct the object. 



**Args:**
 
 - <b>`config`</b>:  The configuration for the openstack runner manager. 


---

#### <kbd>property</kbd> name_prefix

The prefix of runner names. 



**Returns:**
  The prefix of the runner names managed by this class. 



---

<a href="../../github-runner-manager/src/github_runner_manager/openstack_cloud/openstack_runner_manager.py#L350"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../../github-runner-manager/src/github_runner_manager/openstack_cloud/openstack_runner_manager.py#L179"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `create_runner`

```python
create_runner(registration_token: str) → str
```

Create a self-hosted runner. 



**Args:**
 
 - <b>`registration_token`</b>:  The GitHub registration token for registering runners. 



**Raises:**
 
 - <b>`MissingServerConfigError`</b>:  Unable to create runner due to missing configuration. 
 - <b>`RunnerCreateError`</b>:  Unable to create runner due to OpenStack issues. 



**Returns:**
 Instance ID of the runner. 

---

<a href="../../github-runner-manager/src/github_runner_manager/openstack_cloud/openstack_runner_manager.py#L285"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `delete_runner`

```python
delete_runner(instance_id: str, remove_token: str) → RunnerMetrics | None
```

Delete self-hosted runners. 



**Args:**
 
 - <b>`instance_id`</b>:  The instance id of the runner to delete. 
 - <b>`remove_token`</b>:  The GitHub remove token. 



**Returns:**
 Any metrics collected during the deletion of the runner. 

---

<a href="../../github-runner-manager/src/github_runner_manager/openstack_cloud/openstack_runner_manager.py#L319"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `flush_runners`

```python
flush_runners(remove_token: str, busy: bool = False) → Iterator[RunnerMetrics]
```

Remove idle and/or busy runners. 



**Args:**
  remove_token: 
 - <b>`busy`</b>:  If false, only idle runners are removed. If true, both idle and busy runners are  removed. 



**Returns:**
 Any metrics retrieved from flushed runners. 

---

<a href="../../github-runner-manager/src/github_runner_manager/openstack_cloud/openstack_runner_manager.py#L222"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_runner`

```python
get_runner(instance_id: str) → CloudRunnerInstance | None
```

Get a self-hosted runner by instance id. 



**Args:**
 
 - <b>`instance_id`</b>:  The instance id. 



**Returns:**
 Information on the runner instance. 

---

<a href="../../github-runner-manager/src/github_runner_manager/openstack_cloud/openstack_runner_manager.py#L251"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_runners`

```python
get_runners(
    states: Optional[Sequence[CloudRunnerState]] = None
) → tuple[CloudRunnerInstance, ]
```

Get self-hosted runners by state. 



**Args:**
 
 - <b>`states`</b>:  Filter for the runners with these github states. If None all states will be  included. 



**Returns:**
 Information on the runner instances. 



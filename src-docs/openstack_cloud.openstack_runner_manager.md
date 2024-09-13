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

<a href="../src/openstack_cloud/openstack_runner_manager.py#L71"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `OpenStackCloudConfig`
Configuration for OpenStack cloud authorisation information. 



**Attributes:**
 
 - <b>`clouds_config`</b>:  The clouds.yaml. 
 - <b>`cloud`</b>:  The cloud name to connect to. 

<a href="../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(clouds_config: dict[str, dict], cloud: str) → None
```









---

<a href="../src/openstack_cloud/openstack_runner_manager.py#L84"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `OpenStackServerConfig`
Configuration for OpenStack server. 



**Attributes:**
 
 - <b>`image`</b>:  The image name for runners to use. 
 - <b>`flavor`</b>:  The flavor name for runners to use. 
 - <b>`network`</b>:  The network name for runners to use. 

<a href="../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(image: str, flavor: str, network: str) → None
```









---

<a href="../src/openstack_cloud/openstack_runner_manager.py#L112"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `OpenStackRunnerManager`
Manage self-hosted runner on OpenStack cloud. 



**Attributes:**
 
 - <b>`name_prefix`</b>:  The name prefix of the runners created. 

<a href="../src/openstack_cloud/openstack_runner_manager.py#L120"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    manager_name: str,
    prefix: str,
    cloud_config: OpenStackCloudConfig,
    server_config: OpenStackServerConfig | None,
    runner_config: GitHubRunnerConfig,
    service_config: SupportServiceConfig
) → None
```

Construct the object. 



**Args:**
 
 - <b>`manager_name`</b>:  A name to identify this manager. 
 - <b>`prefix`</b>:  The prefix to runner name. 
 - <b>`cloud_config`</b>:  The configuration for OpenStack authorisation. 
 - <b>`server_config`</b>:  The configuration for creating OpenStack server. Unable to create  runner if None. 
 - <b>`runner_config`</b>:  The configuration for the runner. 
 - <b>`service_config`</b>:  The configuration of supporting services of the runners. 


---

#### <kbd>property</kbd> name_prefix

The prefix of runner names. 



**Returns:**
  The prefix of the runner names managed by this class. 



---

<a href="../src/openstack_cloud/openstack_runner_manager.py#L320"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/openstack_cloud/openstack_runner_manager.py#L170"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/openstack_cloud/openstack_runner_manager.py#L269"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/openstack_cloud/openstack_runner_manager.py#L295"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/openstack_cloud/openstack_runner_manager.py#L215"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/openstack_cloud/openstack_runner_manager.py#L237"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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



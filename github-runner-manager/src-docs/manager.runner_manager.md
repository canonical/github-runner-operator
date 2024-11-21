<!-- markdownlint-disable -->

<a href="../src/github_runner_manager/manager/runner_manager.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `manager.runner_manager`
Class for managing the GitHub self-hosted runners hosted on cloud instances. 



---

<a href="../src/github_runner_manager/manager/runner_manager.py#L35"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `FlushMode`
Strategy for flushing runners. 



**Attributes:**
 
 - <b>`FLUSH_IDLE`</b>:  Flush idle runners. 
 - <b>`FLUSH_BUSY`</b>:  Flush busy runners. 





---

<a href="../src/github_runner_manager/manager/runner_manager.py#L47"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerInstance`
Represents an instance of runner. 



**Attributes:**
 
 - <b>`name`</b>:  Full name of the runner. Managed by the cloud runner manager. 
 - <b>`instance_id`</b>:  ID of the runner. Managed by the runner manager. 
 - <b>`health`</b>:  The health state of the runner. 
 - <b>`github_state`</b>:  State on github. 
 - <b>`cloud_state`</b>:  State on cloud. 

<a href="../src/github_runner_manager/manager/runner_manager.py#L65"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    cloud_instance: CloudRunnerInstance,
    github_info: SelfHostedRunner | None
)
```

Construct an instance. 



**Args:**
 
 - <b>`cloud_instance`</b>:  Information on the cloud instance. 
 - <b>`github_info`</b>:  Information on the GitHub of the runner. 





---

<a href="../src/github_runner_manager/manager/runner_manager.py#L81"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerManagerConfig`
Configuration for the runner manager. 



**Attributes:**
 
 - <b>`name`</b>:  A name to identify this manager. 
 - <b>`token`</b>:  GitHub personal access token to query GitHub API. 
 - <b>`path`</b>:  Path to GitHub repository or organization to registry the runners. 

<a href="../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(name: str, token: str, path: GitHubOrg | GitHubRepo) → None
```









---

<a href="../src/github_runner_manager/manager/runner_manager.py#L96"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerManager`
Manage the runners. 



**Attributes:**
 
 - <b>`manager_name`</b>:  A name to identify this manager. 
 - <b>`name_prefix`</b>:  The name prefix of the runners. 

<a href="../src/github_runner_manager/manager/runner_manager.py#L104"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(cloud_runner_manager: CloudRunnerManager, config: RunnerManagerConfig)
```

Construct the object. 



**Args:**
 
 - <b>`cloud_runner_manager`</b>:  For managing the cloud instance of the runner. 
 - <b>`config`</b>:  Configuration of this class. 




---

<a href="../src/github_runner_manager/manager/runner_manager.py#L242"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `cleanup`

```python
cleanup() → dict[Type[Event], int]
```

Run cleanup of the runners and other resources. 



**Returns:**
  Stats on metrics events issued during the cleanup of runners. 

---

<a href="../src/github_runner_manager/manager/runner_manager.py#L123"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `create_runners`

```python
create_runners(num: int) → tuple[str, ]
```

Create runners. 



**Args:**
 
 - <b>`num`</b>:  Number of runners to create. 



**Returns:**
 List of instance ID of the runners. 

---

<a href="../src/github_runner_manager/manager/runner_manager.py#L198"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `delete_runners`

```python
delete_runners(num: int) → dict[Type[Event], int]
```

Delete runners. 



**Args:**
 
 - <b>`num`</b>:  The number of runner to delete. 



**Returns:**
 Stats on metrics events issued during the deletion of runners. 

---

<a href="../src/github_runner_manager/manager/runner_manager.py#L214"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `flush_runners`

```python
flush_runners(
    flush_mode: FlushMode = <FlushMode.FLUSH_IDLE: 1>
) → dict[Type[Event], int]
```

Delete runners according to state. 



**Args:**
 
 - <b>`flush_mode`</b>:  The type of runners affect by the deletion. 



**Returns:**
 Stats on metrics events issued during the deletion of runners. 

---

<a href="../src/github_runner_manager/manager/runner_manager.py#L140"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_runners`

```python
get_runners(
    github_states: Optional[Sequence[GitHubRunnerState]] = None,
    cloud_states: Optional[Sequence[CloudRunnerState]] = None
) → tuple[RunnerInstance]
```

Get information on runner filter by state. 

Only runners that has cloud instance are returned. 



**Args:**
 
 - <b>`github_states`</b>:  Filter for the runners with these github states. If None all  states will be included. 
 - <b>`cloud_states`</b>:  Filter for the runners with these cloud states. If None all states  will be included. 



**Returns:**
 Information on the runners. 



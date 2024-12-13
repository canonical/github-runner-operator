<!-- markdownlint-disable -->

<a href="../../github-runner-manager/src/github_runner_manager/manager/cloud_runner_manager.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `manager.cloud_runner_manager`
Interface of manager of runner instance on clouds. 



---

<a href="../../github-runner-manager/src/github_runner_manager/manager/cloud_runner_manager.py#L25"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `HealthState`
Health state of the runners. 



**Attributes:**
 
 - <b>`HEALTHY`</b>:  The runner is healthy. 
 - <b>`UNHEALTHY`</b>:  The runner is not healthy. 
 - <b>`UNKNOWN`</b>:  Unable to get the health state. 





---

<a href="../../github-runner-manager/src/github_runner_manager/manager/cloud_runner_manager.py#L53"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `CloudRunnerState`
Represent state of the instance hosting the runner. 



**Attributes:**
 
 - <b>`CREATED`</b>:  The instance is created. 
 - <b>`ACTIVE`</b>:  The instance is active and running. 
 - <b>`DELETED`</b>:  The instance is deleted. 
 - <b>`ERROR`</b>:  The instance has encountered error and not running. 
 - <b>`STOPPED`</b>:  The instance has stopped. 
 - <b>`UNKNOWN`</b>:  The state of the instance is not known. 
 - <b>`UNEXPECTED`</b>:  An unknown state not accounted by the developer is encountered. 





---

<a href="../../github-runner-manager/src/github_runner_manager/manager/cloud_runner_manager.py#L111"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `CloudInitStatus`
Represents the state of cloud-init script. 

The cloud init script is used to launch ephemeral GitHub runners. If the script is being initialized, GitHub runner is listening for jobs or GitHub runner is running the job, the cloud-init script should report "running" status. 

Refer to the official documentation on cloud-init status: https://cloudinit.readthedocs.io/en/latest/howto/status.html. 



**Attributes:**
 
 - <b>`NOT_STARTED`</b>:  The cloud-init script has not yet been started. 
 - <b>`RUNNING`</b>:  The cloud-init script is running. 
 - <b>`DONE`</b>:  The cloud-init script has completed successfully. 
 - <b>`ERROR`</b>:  There was an error while running the cloud-init script. 
 - <b>`DEGRADED`</b>:  There was a non-critical issue while running the cloud-inits script. 
 - <b>`DISABLED`</b>:  Cloud init was disabled by other system configurations. 





---

<a href="../../github-runner-manager/src/github_runner_manager/manager/cloud_runner_manager.py#L138"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `GitHubRunnerConfig`
Configuration for GitHub runner spawned. 



**Attributes:**
 
 - <b>`github_path`</b>:  The GitHub organization or repository for runners to connect to. 
 - <b>`labels`</b>:  The labels to add to runners. 

<a href="../../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(github_path: GitHubOrg | GitHubRepo, labels: list[str]) → None
```









---

<a href="../../github-runner-manager/src/github_runner_manager/manager/cloud_runner_manager.py#L151"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `SupportServiceConfig`
Configuration for supporting services for runners. 



**Attributes:**
 
 - <b>`proxy_config`</b>:  The proxy configuration. 
 - <b>`dockerhub_mirror`</b>:  The dockerhub mirror to use for runners. 
 - <b>`ssh_debug_connections`</b>:  The information on the ssh debug services. 
 - <b>`repo_policy_compliance`</b>:  The configuration of the repo policy compliance service. 

<a href="../../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    proxy_config: ProxyConfig | None,
    dockerhub_mirror: str | None,
    ssh_debug_connections: list[SSHDebugConnection] | None,
    repo_policy_compliance: RepoPolicyComplianceConfig | None
) → None
```









---

<a href="../../github-runner-manager/src/github_runner_manager/manager/cloud_runner_manager.py#L168"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `CloudRunnerInstance`
Information on the runner on the cloud. 



**Attributes:**
 
 - <b>`name`</b>:  Name of the instance hosting the runner. 
 - <b>`instance_id`</b>:  ID of the instance. 
 - <b>`health`</b>:  Health state of the runner. 
 - <b>`state`</b>:  State of the instance hosting the runner. 

<a href="../../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    name: str,
    instance_id: str,
    health: HealthState,
    state: CloudRunnerState
) → None
```









---

<a href="../../github-runner-manager/src/github_runner_manager/manager/cloud_runner_manager.py#L185"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `CloudRunnerManager`
Manage runner instance on cloud. 



**Attributes:**
 
 - <b>`name_prefix`</b>:  The name prefix of the self-hosted runners. 


---

#### <kbd>property</kbd> name_prefix

Get the name prefix of the self-hosted runners. 



---

<a href="../../github-runner-manager/src/github_runner_manager/manager/cloud_runner_manager.py#L241"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `cleanup`

```python
cleanup(remove_token: str) → Iterator[RunnerMetrics]
```

Cleanup runner and resource on the cloud. 

Perform health check on runner and delete the runner if it fails. 



**Args:**
 
 - <b>`remove_token`</b>:  The GitHub remove token for removing runners. 

---

<a href="../../github-runner-manager/src/github_runner_manager/manager/cloud_runner_manager.py#L197"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `create_runner`

```python
create_runner(registration_token: str) → str
```

Create a self-hosted runner. 



**Args:**
 
 - <b>`registration_token`</b>:  The GitHub registration token for registering runners. 

---

<a href="../../github-runner-manager/src/github_runner_manager/manager/cloud_runner_manager.py#L222"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `delete_runner`

```python
delete_runner(instance_id: str, remove_token: str) → RunnerMetrics | None
```

Delete self-hosted runner. 



**Args:**
 
 - <b>`instance_id`</b>:  The instance id of the runner to delete. 
 - <b>`remove_token`</b>:  The GitHub remove token. 

---

<a href="../../github-runner-manager/src/github_runner_manager/manager/cloud_runner_manager.py#L231"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `flush_runners`

```python
flush_runners(remove_token: str, busy: bool = False) → Iterator[RunnerMetrics]
```

Stop all runners. 



**Args:**
 
 - <b>`remove_token`</b>:  The GitHub remove token for removing runners. 
 - <b>`busy`</b>:  If false, only idle runners are removed. If true, both idle and busy runners are  removed. 

---

<a href="../../github-runner-manager/src/github_runner_manager/manager/cloud_runner_manager.py#L205"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_runner`

```python
get_runner(instance_id: str) → CloudRunnerInstance | None
```

Get a self-hosted runner by instance id. 



**Args:**
 
 - <b>`instance_id`</b>:  The instance id. 

---

<a href="../../github-runner-manager/src/github_runner_manager/manager/cloud_runner_manager.py#L213"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_runners`

```python
get_runners(states: Sequence[CloudRunnerState]) → Tuple[CloudRunnerInstance]
```

Get self-hosted runners by state. 



**Args:**
 
 - <b>`states`</b>:  Filter for the runners with these github states. If None all states will be  included. 



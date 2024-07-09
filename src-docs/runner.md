<!-- markdownlint-disable -->

<a href="../src/reactive/runner.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `runner`
Module which contains code to spawn a runner reactively. 

**Global Variables**
---------------
- **APROXY_ARM_REVISION**
- **APROXY_AMD_REVISION**
- **FILE_SIZE_BYTES_LIMIT**
- **PRE_JOB_METRICS_FILE_NAME**
- **POST_JOB_METRICS_FILE_NAME**
- **RUNNER_INSTALLED_TS_FILE_NAME**

---

<a href="../src/reactive/runner.py#L12"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `reactive_runner`

```python
reactive_runner(mq_uri: str, queue_name: str) → None
```

Spawn a runner reactively. 



**Args:**
 
 - <b>`mq_uri`</b>:  The URI of the message queue. 
 - <b>`queue_name`</b>:  The name of the queue. 


---

<a href="../src/metrics/runner.py#L107"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `extract`

```python
extract(
    metrics_storage_manager: StorageManager,
    ignore_runners: set[str]
) → Iterator[RunnerMetrics]
```

Extract metrics from runners. 

The metrics are extracted from the metrics storage of the runners. Orphan storages are cleaned up. 

If corrupt data is found, the metrics are not processed further and the storage is moved to a special quarantine directory, as this may indicate that a malicious runner is trying to manipulate the files on the storage. 

In order to avoid DoS attacks, the file size is also checked. 



**Args:**
 
 - <b>`metrics_storage_manager`</b>:  The metrics storage manager. 
 - <b>`ignore_runners`</b>:  The set of runners to ignore. 



**Yields:**
 Extracted runner metrics of a particular runner. 


---

<a href="../src/metrics/runner.py#L139"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `issue_events`

```python
issue_events(
    runner_metrics: RunnerMetrics,
    flavor: str,
    job_metrics: Optional[GithubJobMetrics]
) → set[Type[Event]]
```

Issue the metrics events for a runner. 



**Args:**
 
 - <b>`runner_metrics`</b>:  The metrics for the runner. 
 - <b>`flavor`</b>:  The flavor of the runner. 
 - <b>`job_metrics`</b>:  The metrics about the job run by the runner. 



**Returns:**
 A set of issued events. 


---

<a href="../src/reactive/runner.py"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `CodeInformation`
Information about a status code. 



**Attributes:**
 
 - <b>`code`</b>:  The status code. 





---

<a href="../src/reactive/runner.py"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `CreateRunnerConfig`
The configuration values for creating a single runner instance. 



**Attributes:**
 
 - <b>`image`</b>:  Name of the image to launch the LXD instance with. 
 - <b>`resources`</b>:  Resource setting for the LXD instance. 
 - <b>`binary_path`</b>:  Path to the runner binary. 
 - <b>`registration_token`</b>:  Token for registering the runner on GitHub. 
 - <b>`arch`</b>:  Current machine architecture. 

<a href="../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    image: str,
    resources: VirtualMachineResources,
    binary_path: Path,
    registration_token: str,
    arch: Arch = <Arch.X64: 'x64'>
) → None
```









---

<a href="../src/reactive/runner.py"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `PostJobMetrics`
Metrics for the post-job phase of a runner. 



**Attributes:**
 
 - <b>`timestamp`</b>:  The UNIX time stamp of the time at which the event was originally issued. 
 - <b>`status`</b>:  The status of the job. 
 - <b>`status_info`</b>:  More information about the status. 





---

<a href="../src/reactive/runner.py"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `PostJobStatus`
The status of the post-job phase of a runner. 



**Attributes:**
 
 - <b>`NORMAL`</b>:  Represents a normal post-job. 
 - <b>`ABNORMAL`</b>:  Represents an error with post-job. 
 - <b>`REPO_POLICY_CHECK_FAILURE`</b>:  Represents an error with repo-policy-compliance check. 





---

<a href="../src/reactive/runner.py"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `PreJobMetrics`
Metrics for the pre-job phase of a runner. 



**Attributes:**
 
 - <b>`timestamp`</b>:  The UNIX time stamp of the time at which the event was originally issued. 
 - <b>`workflow`</b>:  The workflow name. 
 - <b>`workflow_run_id`</b>:  The workflow run id. 
 - <b>`repository`</b>:  The repository path in the format '<owner>/<repo>'. 
 - <b>`event`</b>:  The github event. 





---

<a href="../src/reactive/runner.py"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `Runner`
Single instance of GitHub self-hosted runner. 



**Attributes:**
 
 - <b>`runner_application`</b>:  The runner application directory path 
 - <b>`env_file`</b>:  The runner environment source .env file path. 
 - <b>`config_script`</b>:  The runner configuration script file path. 
 - <b>`runner_script`</b>:  The runner start script file path. 
 - <b>`pre_job_script`</b>:  The runner pre_job script file path. This is referenced in the env_file in  the ACTIONS_RUNNER_HOOK_JOB_STARTED environment variable. 

<a href="../src/runner.py#L125"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    clients: RunnerManagerClients,
    runner_config: RunnerConfig,
    runner_status: RunnerStatus,
    instance: Optional[LxdInstance] = None
)
```

Construct the runner instance. 



**Args:**
 
 - <b>`clients`</b>:  Clients to access various services. 
 - <b>`runner_config`</b>:  Configuration of the runner instance. 
 - <b>`runner_status`</b>:  Status info of the given runner. 
 - <b>`instance`</b>:  LXD instance of the runner if already created. 




---

<a href="../src/runner.py#L148"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `create`

```python
create(config: CreateRunnerConfig) → None
```

Create the runner instance on LXD and register it on GitHub. 



**Args:**
 
 - <b>`config`</b>:  The instance config to create the LXD VMs and configure GitHub runner with. 



**Raises:**
 
 - <b>`RunnerCreateError`</b>:  Unable to create an LXD instance for runner. 

---

<a href="../src/runner.py#L276"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `pull_logs`

```python
pull_logs() → None
```

Pull the logs of the runner into a directory. 

Expects the runner to have an instance. 



**Raises:**
 
 - <b>`RunnerLogsError`</b>:  If the runner logs could not be pulled. 

---

<a href="../src/runner.py#L241"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `remove`

```python
remove(remove_token: Optional[str]) → None
```

Remove this runner instance from LXD and GitHub. 



**Args:**
 
 - <b>`remove_token`</b>:  Token for removing the runner on GitHub. 



**Raises:**
 
 - <b>`RunnerRemoveError`</b>:  Failure in removing runner. 


---

<a href="../src/reactive/runner.py"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerMetrics`
Metrics for a runner. 



**Attributes:**
 
 - <b>`installed_timestamp`</b>:  The UNIX time stamp of the time at which the runner was installed. 
 - <b>`pre_job`</b>:  The metrics for the pre-job phase. 
 - <b>`post_job`</b>:  The metrics for the post-job phase. 
 - <b>`runner_name`</b>:  The name of the runner. 





---

<a href="../src/reactive/runner.py"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `Snap`
This class represents a snap installation. 



**Attributes:**
 
 - <b>`name`</b>:  The snap application name. 
 - <b>`channel`</b>:  The channel to install the snap from. 
 - <b>`revision`</b>:  The revision number of the snap installation. 





---

<a href="../src/reactive/runner.py"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `WgetExecutable`
The executable to be installed through wget. 



**Attributes:**
 
 - <b>`url`</b>:  The URL of the executable binary. 
 - <b>`cmd`</b>:  Executable command name. E.g. yq_linux_amd64 -> yq 

<a href="../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(url: str, cmd: str) → None
```










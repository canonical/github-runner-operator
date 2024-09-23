<!-- markdownlint-disable -->

<a href="../src/runner.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `runner`
Manage the lifecycle of runners. 

The `Runner` class stores the information on the runners and manages the lifecycle of the runners on LXD and GitHub. 

The `RunnerManager` class from `runner_manager.py` creates and manages a collection of `Runner` instances. 

**Global Variables**
---------------
- **APROXY_ARM_REVISION**
- **APROXY_AMD_REVISION**


---

<a href="../src/runner.py#L61"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `Snap`
This class represents a snap installation. 



**Attributes:**
 
 - <b>`name`</b>:  The snap application name. 
 - <b>`channel`</b>:  The channel to install the snap from. 
 - <b>`revision`</b>:  The revision number of the snap installation. 





---

<a href="../src/runner.py#L75"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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









---

<a href="../src/runner.py#L88"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/runner.py#L107"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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



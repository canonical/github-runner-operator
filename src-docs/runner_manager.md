<!-- markdownlint-disable -->

<a href="../src/reactive/runner_manager.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `runner_manager`
Module for managing reactive runners. 

**Global Variables**
---------------
- **RUNNER_INSTALLED_TS_FILE_NAME**
- **REMOVED_RUNNER_LOG_STR**
- **REACTIVE_RUNNER_LOG_PATH**
- **REACTIVE_RUNNER_SCRIPT_FILE**
- **REACTIVE_RUNNER_TIMEOUT_STR**
- **PYTHON_BIN**
- **PS_COMMAND_LINE_LIST**
- **TIMEOUT_COMMAND**
- **UBUNTU_USER**

---

<a href="../src/reactive/runner_manager.py#L35"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `reconcile`

```python
reconcile(quantity: int, config: ReactiveRunnerConfig) → int
```

Spawn a runner reactively. 



**Args:**
 
 - <b>`quantity`</b>:  The number of runners to spawn. 
 - <b>`config`</b>:  The configuration for the reactive runner. 



**Raises:**
 
 - <b>`ReactiveRunnerError`</b>:  If the runner fails to spawn. 


---

<a href="../src/reactive/runner_manager.py"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerManager`
Manage a group of runners according to configuration. 



**Attributes:**
 
 - <b>`runner_bin_path`</b>:  The github runner app scripts path. 
 - <b>`cron_path`</b>:  The path to runner build image cron job. 

<a href="../src/runner_manager.py#L70"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    app_name: str,
    unit: int,
    runner_manager_config: RunnerManagerConfig
) → None
```

Construct RunnerManager object for creating and managing runners. 



**Args:**
 
 - <b>`app_name`</b>:  An name for the set of runners. 
 - <b>`unit`</b>:  Unit number of the set of runners. 
 - <b>`runner_manager_config`</b>:  Configuration for the runner manager. 




---

<a href="../src/utilities.py#L806"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `build_runner_image`

```python
build_runner_image() → None
```

Build the LXD image for hosting runner. 

Build container image in test mode, else virtual machine image. 



**Raises:**
 
 - <b>`SubprocessError`</b>:  Unable to build the LXD image. 

---

<a href="../src/runner_manager.py#L112"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `check_runner_bin`

```python
check_runner_bin() → bool
```

Check if runner binary exists. 



**Returns:**
  Whether runner bin exists. 

---

<a href="../src/runner_manager.py#L617"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `flush`

```python
flush(mode: FlushMode = <FlushMode.FLUSH_IDLE: 1>) → int
```

Remove existing runners. 



**Args:**
 
 - <b>`mode`</b>:  Strategy for flushing runners. 



**Raises:**
 
 - <b>`GithubClientError`</b>:  If there was an error getting remove-token to unregister runners                 from GitHub. 



**Returns:**
 Number of runners removed. 

---

<a href="../src/runner_manager.py#L213"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_github_info`

```python
get_github_info() → Iterator[RunnerInfo]
```

Get information on the runners from GitHub. 



**Returns:**
  List of information from GitHub on runners. 

---

<a href="../src/utilities.py#L120"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_latest_runner_bin_url`

```python
get_latest_runner_bin_url(os_name: str = 'linux') → RunnerApplication
```

Get the URL for the latest runner binary. 

The runner binary URL changes when a new version is available. 



**Args:**
 
 - <b>`os_name`</b>:  Name of operating system. 



**Raises:**
 
 - <b>`RunnerBinaryError`</b>:  If an error occurred while fetching runner application info. 



**Returns:**
 Information on the runner application. 

---

<a href="../src/runner_manager.py#L798"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `has_runner_image`

```python
has_runner_image() → bool
```

Check if the runner image exists. 



**Returns:**
  Whether the runner image exists. 

---

<a href="../src/runner_manager.py#L520"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `reconcile`

```python
reconcile(quantity: int, resources: VirtualMachineResources) → int
```

Bring runners in line with target. 



**Args:**
 
 - <b>`quantity`</b>:  Number of intended runners. 
 - <b>`resources`</b>:  Configuration of the virtual machine resources. 



**Returns:**
 Difference between intended runners and actual runners. 

---

<a href="../src/runner_manager.py#L821"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `schedule_build_runner_image`

```python
schedule_build_runner_image() → None
```

Install cron job for building runner image. 

---

<a href="../src/utilities.py#L143"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `update_runner_bin`

```python
update_runner_bin(binary: RunnerApplication) → None
```

Download a runner file, replacing the current copy. 

Remove the existing runner binary to prevent it from being used. This is done to prevent security issues arising from outdated runner binaries containing security flaws. The newest version of runner binary should always be used. 



**Args:**
 
 - <b>`binary`</b>:  Information on the runner binary to download. 



**Raises:**
 
 - <b>`RunnerBinaryError`</b>:  If there was an error updating runner binary info. 


---

<a href="../src/reactive/runner_manager.py#L24"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `ReactiveRunnerError`
Raised when a reactive runner error occurs. 





---

<a href="../src/reactive/runner_manager.py#L28"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `ReactiveRunnerConfig`
ReactiveRunnerConfig(mq_uri: str, queue_name: str) 

<a href="../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(mq_uri: str, queue_name: str) → None
```










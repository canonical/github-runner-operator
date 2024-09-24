<!-- markdownlint-disable -->

<a href="../src/runner_manager.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `runner_manager`
Runner Manager manages the runners on LXD and GitHub. 

**Global Variables**
---------------
- **RUNNER_INSTALLED_TS_FILE_NAME**
- **REMOVED_RUNNER_LOG_STR**


---

<a href="../src/runner_manager.py#L63"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `LXDRunnerManager`
Manage a group of runners according to configuration. 



**Attributes:**
 
 - <b>`runner_bin_path`</b>:  The github runner app scripts path. 
 - <b>`cron_path`</b>:  The path to runner build image cron job. 

<a href="../src/runner_manager.py#L74"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    app_name: str,
    unit: int,
    runner_manager_config: LXDRunnerManagerConfig
) → None
```

Construct RunnerManager object for creating and managing runners. 



**Args:**
 
 - <b>`app_name`</b>:  An name for the set of runners. 
 - <b>`unit`</b>:  Unit number of the set of runners. 
 - <b>`runner_manager_config`</b>:  Configuration for the runner manager. 




---

<a href="../.tox/src-docs/lib/python3.10/site-packages/github_runner_manager/utilities.py#L797"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `build_runner_image`

```python
build_runner_image() → None
```

Build the LXD image for hosting runner. 

Build container image in test mode, else virtual machine image. 



**Raises:**
 
 - <b>`SubprocessError`</b>:  Unable to build the LXD image. 

---

<a href="../src/runner_manager.py#L116"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `check_runner_bin`

```python
check_runner_bin() → bool
```

Check if runner binary exists. 



**Returns:**
  Whether runner bin exists. 

---

<a href="../src/runner_manager.py#L608"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `flush`

```python
flush(mode: LXDFlushMode = <LXDFlushMode.FLUSH_IDLE: 1>) → int
```

Remove existing runners. 



**Args:**
 
 - <b>`mode`</b>:  Strategy for flushing runners. 



**Raises:**
 
 - <b>`GithubClientError`</b>:  If there was an error getting remove-token to unregister runners                 from GitHub. 



**Returns:**
 Number of runners removed. 

---

<a href="../src/runner_manager.py#L217"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_github_info`

```python
get_github_info() → Iterator[RunnerInfo]
```

Get information on the runners from GitHub. 



**Returns:**
  List of information from GitHub on runners. 

---

<a href="../.tox/src-docs/lib/python3.10/site-packages/github_runner_manager/utilities.py#L124"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/runner_manager.py#L789"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `has_runner_image`

```python
has_runner_image() → bool
```

Check if the runner image exists. 



**Returns:**
  Whether the runner image exists. 

---

<a href="../src/runner_manager.py#L526"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/runner_manager.py#L812"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `schedule_build_runner_image`

```python
schedule_build_runner_image() → None
```

Install cron job for building runner image. 

---

<a href="../.tox/src-docs/lib/python3.10/site-packages/github_runner_manager/utilities.py#L147"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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



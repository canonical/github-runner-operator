<!-- markdownlint-disable -->

<a href="../src/runner_manager.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `runner_manager.py`
Runner Manager manages the runners on LXD and GitHub. 



---

## <kbd>class</kbd> `RunnerInfo`
Information from GitHub of a runner. 

Used as a returned type to method querying runner information. 





---

## <kbd>class</kbd> `RunnerManager`
Manage a group of runners according to configuration. 

<a href="../src/runner_manager.py#L92"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(
    app_name: str,
    unit: int,
    runner_manager_config: RunnerManagerConfig,
    proxies: ProxySetting = {}
) → None
```

Construct RunnerManager object for creating and managing runners. 



**Args:**
 
 - <b>`app_name`</b>:  An name for the set of runners. 
 - <b>`unit`</b>:  Unit number of the set of runners. 
 - <b>`runner_manager_config`</b>:  Configuration for the runner manager. 
 - <b>`proxies`</b>:  HTTP proxy settings. 




---

<a href="../src/runner_manager.py#L153"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `check_runner_bin`

```python
check_runner_bin() → bool
```

Check if runner binary exists. 



**Returns:**
  Whether runner bin exists. 

---

<a href="../src/runner_manager.py#L435"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `flush`

```python
flush(flush_busy: bool = True) → int
```

Remove existing runners. 



**Args:**
 
 - <b>`flush_busy`</b>:  Whether to flush busy runners as well. 



**Returns:**
 Number of runners removed. 

---

<a href="../src/runner_manager.py#L266"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_github_info`

```python
get_github_info() → Iterator[RunnerInfo]
```

Get information on the runners from GitHub. 



**Returns:**
  List of information from GitHub on runners. 

---

<a href="../src/utilities.py#L161"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_latest_runner_bin_url`

```python
get_latest_runner_bin_url(
    os_name: str = 'linux',
    arch_name: str = 'x64'
) → RunnerApplication
```

Get the URL for the latest runner binary. 

The runner binary URL changes when a new version is available. 



**Args:**
 
 - <b>`os_name`</b>:  Name of operating system. 
 - <b>`arch_name`</b>:  Name of architecture. 



**Returns:**
 Information on the runner application. 

---

<a href="../src/runner_manager.py#L337"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `reconcile`

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

<a href="../src/utilities.py#L199"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `update_runner_bin`

```python
update_runner_bin(binary: RunnerApplication) → None
```

Download a runner file, replacing the current copy. 

Remove the existing runner binary to prevent it from being used. This is done to prevent security issues arising from outdated runner binaries containing security flaws. The newest version of runner binary should always be used. 



**Args:**
 
 - <b>`binary`</b>:  Information on the runner binary to download. 


---

## <kbd>class</kbd> `RunnerManagerConfig`
Configuration of runner manager. 

Attrs:  path: GitHub repository path in the format '<owner>/<repo>', or the  GitHub organization name.  token: GitHub personal access token to register runner to the  repository or organization.  image: Name of the image for creating LXD instance.  service_token: Token for accessing local service.  lxd_storage_path: Path to be used as LXD storage.  issue_metrics: Whether to issue metrics. 






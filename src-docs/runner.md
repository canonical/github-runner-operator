<!-- markdownlint-disable -->

<a href="../src/lxd_cloud/runner.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `runner`
Manage the lifecycle of runners. 

The `Runner` class stores the information on the runners and manages the lifecycle of the runners on LXD and GitHub. 

The `RunnerManager` class from `runner_manager.py` creates and manages a collection of `Runner` instances. 

**Global Variables**
---------------
- **APROXY_ARM_REVISION**
- **APROXY_AMD_REVISION**


---

<a href="../src/lxd_cloud/runner.py#L54"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `Snap`
This class represents a snap installation. 





---

<a href="../src/lxd_cloud/runner.py#L62"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `WgetExecutable`
The executable to be installed through wget. 



**Args:**
 
 - <b>`url`</b>:  The URL of the executable binary. 
 - <b>`cmd`</b>:  Executable command name. E.g. yq_linux_amd64 -> yq 

<a href="../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(url: str, cmd: str) → None
```









---

<a href="../src/lxd_cloud/runner.py#L75"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `CreateRunnerConfig`
The configuration values for creating a single runner instance. 



**Args:**
 
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

<a href="../src/lxd_cloud/runner.py#L94"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `Runner`
Single instance of GitHub self-hosted runner. 

<a href="../src/lxd_cloud/runner.py#L103"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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
 - <b>`instance`</b>:  LXD instance of the runner if already created. 




---

<a href="../src/lxd_cloud/runner.py#L125"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `create`

```python
create(config: CreateRunnerConfig)
```

Create the runner instance on LXD and register it on GitHub. 



**Args:**
 
 - <b>`config`</b>:  The instance config to create the LXD VMs and configure GitHub runner with. 



**Raises:**
 
 - <b>`RunnerCreateError`</b>:  Unable to create an LXD instance for runner. 

---

<a href="../src/lxd_cloud/runner.py#L162"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `remove`

```python
remove(remove_token: Optional[str]) → None
```

Remove this runner instance from LXD and GitHub. 



**Args:**
 
 - <b>`remove_token`</b>:  Token for removing the runner on GitHub. 



**Raises:**
 
 - <b>`RunnerRemoveError`</b>:  Failure in removing runner. 



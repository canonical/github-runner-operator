<!-- markdownlint-disable -->

<a href="../src/runner.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `runner.py`
Manage the lifecycle of runners. 

The `Runner` class stores the information on the runners and manages the lifecycle of the runners on LXD and GitHub. 

The `RunnerManager` class from `runner_manager.py` creates and manages a collection of `Runner` instances. 



---

## <kbd>class</kbd> `Runner`
Single instance of GitHub self-hosted runner. 



**Attributes:**
 
 - <b>`app_name`</b> (str):  Name of the charm. 
 - <b>`path`</b> (GitHubPath):  Path to GitHub repo or org. 
 - <b>`proxies`</b> (ProxySetting):  HTTP proxy setting for juju charm. 
 - <b>`name`</b> (str):  Name of the runner instance. 
 - <b>`exist`</b> (bool):  Whether the runner instance exists on LXD. 
 - <b>`online`</b> (bool):  Whether GitHub marks this runner as online. 
 - <b>`busy`</b> (bool):  Whether GitHub marks this runner as busy. 

<a href="../src/runner.py#L87"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

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

<a href="../src/runner.py#L117"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `create`

```python
create(
    image: str,
    resources: VirtualMachineResources,
    binary_path: Path,
    registration_token: str
)
```

Create the runner instance on LXD and register it on GitHub. 



**Args:**
 
 - <b>`image`</b>:  Name of the image to launch the LXD instance with. 
 - <b>`resources`</b>:  Resource setting for the LXD instance. 
 - <b>`binary_path`</b>:  Path to the runner binary. 
 - <b>`registration_token`</b>:  Token for registering the runner on GitHub. 



**Raises:**
 
 - <b>`RunnerCreateError`</b>:  Unable to create an LXD instance for runner. 

---

<a href="../src/runner.py#L160"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `remove`

```python
remove(remove_token: str) → None
```

Remove this runner instance from LXD and GitHub. 



**Args:**
 
 - <b>`remove_token`</b>:  Token for removing the runner on GitHub. 



**Raises:**
 
 - <b>`RunnerRemoveError`</b>:  Failure in removing runner. 


---

## <kbd>class</kbd> `Snap`
Snap(name, channel) 





---

## <kbd>class</kbd> `WgetExecutable`
The executable to be installed through wget. 



**Args:**
 
 - <b>`url`</b>:  The URL of the executable binary. 
 - <b>`cmd`</b>:  Executable command name. E.g. yq_linux_amd64 -> yq 






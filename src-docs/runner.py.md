<!-- markdownlint-disable -->

<a href="../src/runner.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `runner.py`
Manage the lifecycle of runners. 

The `Runner` class stores the information on the runners and manages the lifecycle of the runners on LXD and GitHub. 

The `RunnerManager` class from `runner_manager.py` creates and manages a collection of `Runner` instances. 

**Global Variables**
---------------
- **APROXY_ARM_REVISION**
- **APROXY_AMD_REVISION**


---

## <kbd>class</kbd> `CreateRunnerConfig`
The configuration values for creating a single runner instance. 



**Attributes:**
 
 - <b>`image`</b>:  Name of the image to launch the LXD instance with. 
 - <b>`resources`</b>:  Resource setting for the LXD instance. 
 - <b>`binary_path`</b>:  Path to the runner binary. 
 - <b>`registration_token`</b>:  Token for registering the runner on GitHub. 
 - <b>`arch`</b>:  Current machine architecture. 





---

## <kbd>class</kbd> `WgetExecutable`
The executable to be installed through wget. 



**Attributes:**
 
 - <b>`url`</b>:  The URL of the executable binary. 
 - <b>`cmd`</b>:  Executable command name. E.g. yq_linux_amd64 -> yq 






<!-- markdownlint-disable -->

<a href="../src/runner_type.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `runner_type.py`
Types used by both RunnerManager and Runner classes. 



---

## <kbd>class</kbd> `GitHubOrg`
Represent GitHub organization. 




---

<a href="../src/runner_type.py#L53"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `path`

```python
path() → str
```

Return a string representing the path. 


---

## <kbd>class</kbd> `GitHubRepo`
Represent GitHub repository. 




---

<a href="../src/runner_type.py#L41"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `path`

```python
path() → str
```

Return a string representing the path. 


---

## <kbd>class</kbd> `ProxySetting`
Represent HTTP-related proxy settings. 





---

## <kbd>class</kbd> `RunnerByHealth`
Set of runners LXD instance by health state. 





---

## <kbd>class</kbd> `RunnerClients`
Clients for accessing various services. 

Attrs:  github: Used to query GitHub API.  jinja: Used for templating.  lxd: Used to interact with LXD API. 





---

## <kbd>class</kbd> `RunnerConfig`
Configuration for runner. 

Attrs:  app_name: Application name of the charm.  path: GitHub repository path in the format '<owner>/<repo>', or the GitHub organization  name.  proxies: HTTP(S) proxy settings.  lxd_storage_path: Path to be used as LXD storage.  name: Name of the runner.  issue_metrics: Whether to issue metrics. 





---

## <kbd>class</kbd> `RunnerStatus`
Status of runner. 

Attrs:  exist: Whether the runner instance exists on LXD.  online: Whether GitHub marks this runner as online.  busy: Whether GitHub marks this runner as busy. 





---

## <kbd>class</kbd> `VirtualMachineResources`
Virtual machine resource configuration. 






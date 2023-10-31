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



**Attributes:**
 
 - <b>`github`</b>:  Used to query GitHub API. 
 - <b>`jinja`</b>:  Used for templating. 
 - <b>`lxd`</b>:  Used to interact with LXD API. 





---

## <kbd>class</kbd> `RunnerConfig`
Configuration for runner. 



**Attributes:**
 
<<<<<<< HEAD
 - <b>`name`</b>:  Name of the runner. 
=======
>>>>>>> main
 - <b>`app_name`</b>:  Application name of the charm. 
 - <b>`path`</b>:  GitHub repository path in the format '<owner>/<repo>', or the GitHub organization  name. 
 - <b>`proxies`</b>:  HTTP(S) proxy settings. 
 - <b>`lxd_storage_path`</b>:  Path to be used as LXD storage. 
<<<<<<< HEAD
 - <b>`dockerhub_mirror`</b>:  URL of dockerhub mirror to use. 
=======
 - <b>`name`</b>:  Name of the runner. 
 - <b>`issue_metrics`</b>:  Whether to issue metrics. 
>>>>>>> main





---

## <kbd>class</kbd> `RunnerStatus`
Status of runner. 



**Attributes:**
 
 - <b>`exist`</b>:  Whether the runner instance exists on LXD. 
 - <b>`online`</b>:  Whether GitHub marks this runner as online. 
 - <b>`busy`</b>:  Whether GitHub marks this runner as busy. 





---

## <kbd>class</kbd> `VirtualMachineResources`
Virtual machine resource configuration. 






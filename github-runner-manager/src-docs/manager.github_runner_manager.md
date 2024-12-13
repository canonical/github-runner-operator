<!-- markdownlint-disable -->

<a href="../../github-runner-manager/src/github_runner_manager/manager/github_runner_manager.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `manager.github_runner_manager`
Client for managing self-hosted runner on GitHub side. 



---

<a href="../../github-runner-manager/src/github_runner_manager/manager/github_runner_manager.py#L13"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `GitHubRunnerState`
State of the self-hosted runner on GitHub. 



**Attributes:**
 
 - <b>`BUSY`</b>:  Runner is working on a job assigned by GitHub. 
 - <b>`IDLE`</b>:  Runner is waiting to take a job or is running pre-job tasks (i.e.  repo-policy-compliance check). 
 - <b>`OFFLINE`</b>:  Runner is not connected to GitHub. 





---

<a href="../../github-runner-manager/src/github_runner_manager/manager/github_runner_manager.py#L48"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `GitHubRunnerManager`
Manage self-hosted runner on GitHub side. 

<a href="../../github-runner-manager/src/github_runner_manager/manager/github_runner_manager.py#L51"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(prefix: str, token: str, path: GitHubOrg | GitHubRepo)
```

Construct the object. 



**Args:**
 
 - <b>`prefix`</b>:  The prefix in the name to identify the runners managed by this instance. 
 - <b>`token`</b>:  The GitHub personal access token to access the GitHub API. 
 - <b>`path`</b>:  The GitHub repository or organization to register the runners under. 




---

<a href="../../github-runner-manager/src/github_runner_manager/manager/github_runner_manager.py#L87"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `delete_runners`

```python
delete_runners(states: Optional[Iterable[GitHubRunnerState]] = None) → None
```

Delete the self-hosted runners of certain states. 



**Args:**
 
 - <b>`states`</b>:  Filter the runners for these states. If None, all runners are deleted. 

---

<a href="../../github-runner-manager/src/github_runner_manager/manager/github_runner_manager.py#L97"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_registration_token`

```python
get_registration_token() → str
```

Get registration token from GitHub. 

This token is used for registering self-hosted runners. 



**Returns:**
  The registration token. 

---

<a href="../../github-runner-manager/src/github_runner_manager/manager/github_runner_manager.py#L107"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_removal_token`

```python
get_removal_token() → str
```

Get removal token from GitHub. 

This token is used for removing self-hosted runners. 



**Returns:**
  The removal token. 

---

<a href="../../github-runner-manager/src/github_runner_manager/manager/github_runner_manager.py#L63"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_runners`

```python
get_runners(
    states: Optional[Iterable[GitHubRunnerState]] = None
) → tuple[SelfHostedRunner, ]
```

Get info on self-hosted runners of certain states. 



**Args:**
 
 - <b>`states`</b>:  Filter the runners for these states. If None, all runners are returned. 



**Returns:**
 Information on the runners. 



<!-- markdownlint-disable -->

<a href="../src/lxd_cloud/runner_manager_type.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `runner_manager_type`
Types used by RunnerManager class. 



---

<a href="../src/lxd_cloud/runner_manager_type.py#L19"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `FlushMode`
Strategy for flushing runners. 



**Attributes:**
 
 - <b>`FLUSH_IDLE`</b>:  Flush only idle runners. 
 - <b>`FLUSH_IDLE_WAIT_REPO_CHECK`</b>:  Flush only idle runners, then wait until repo-policy-check is  completed for the busy runners. 
 - <b>`FLUSH_BUSY`</b>:  Flush busy runners. 
 - <b>`FLUSH_BUSY_WAIT_REPO_CHECK`</b>:  Wait until the repo-policy-check is completed before  flush of busy runners. 
 - <b>`FORCE_FLUSH_WAIT_REPO_CHECK`</b>:  Force flush the runners (remove lxd instances even on  gh api issues, like invalid token).  Wait until repo-policy-check is completed before force flush of busy runners. 





---

<a href="../src/lxd_cloud/runner_manager_type.py#L41"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerManagerClients`
Clients for accessing various services. 



**Attributes:**
 
 - <b>`github`</b>:  Used to query GitHub API. 
 - <b>`jinja`</b>:  Used for templating. 
 - <b>`lxd`</b>:  Used to interact with LXD API. 

<a href="../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    github: GithubClient,
    jinja: Environment,
    lxd: LxdClient,
    repo: RepoPolicyComplianceClient
) → None
```









---

<a href="../src/lxd_cloud/runner_manager_type.py#L57"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerManagerConfig`
Configuration of runner manager. 



**Attributes:**
 
 - <b>`charm_state`</b>:  The state of the charm. 
 - <b>`image`</b>:  Name of the image for creating LXD instance. 
 - <b>`lxd_storage_path`</b>:  Path to be used as LXD storage. 
 - <b>`path`</b>:  GitHub repository path in the format '<owner>/<repo>', or the  GitHub organization name. 
 - <b>`service_token`</b>:  Token for accessing local service. 
 - <b>`token`</b>:  GitHub personal access token to register runner to the  repository or organization. 
 - <b>`dockerhub_mirror`</b>:  URL of dockerhub mirror to use. 

<a href="../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    charm_state: CharmState,
    image: str,
    lxd_storage_path: Path,
    path: GithubOrg | GithubRepo,
    service_token: str,
    token: str,
    dockerhub_mirror: str | None = None
) → None
```






---

#### <kbd>property</kbd> are_metrics_enabled

Whether metrics for the runners should be collected. 




---

<a href="../src/lxd_cloud/runner_manager_type.py#L88"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerInfo`
Information from GitHub of a runner. 

Used as a returned type to method querying runner information. 



**Attributes:**
 
 - <b>`name`</b>:  Name of the runner. 
 - <b>`status`</b>:  Status of the runner. 
 - <b>`busy`</b>:  Whether the runner has taken a job. 

<a href="../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(name: str, status: GitHubRunnerStatus, busy: bool) → None
```










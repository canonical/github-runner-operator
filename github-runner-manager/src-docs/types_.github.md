<!-- markdownlint-disable -->

<a href="../../github-runner-manager/src/github_runner_manager/types_/github.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `types_.github`
Module containing GitHub API related types. 


---

<a href="../../github-runner-manager/src/github_runner_manager/types_/github.py#L235"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `parse_github_path`

```python
parse_github_path(path_str: 'str', runner_group: 'str') → GitHubPath
```

Parse GitHub path. 



**Args:**
 
 - <b>`path_str`</b>:  GitHub path in string format. 
 - <b>`runner_group`</b>:  Runner group name for GitHub organization. If the path is  a repository this argument is ignored. 



**Raises:**
 
 - <b>`ValueError`</b>:  if an invalid path string was given. 



**Returns:**
 GithubPath object representing the GitHub repository, or the GitHub organization with runner group information. 


---

<a href="../../github-runner-manager/src/github_runner_manager/types_/github.py#L18"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `GitHubRunnerStatus`
Status of runner on GitHub. 



**Attributes:**
 
 - <b>`ONLINE`</b>:  Represents an online runner status. 
 - <b>`OFFLINE`</b>:  Represents an offline runner status. 





---

<a href="../../github-runner-manager/src/github_runner_manager/types_/github.py#L32"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerApplication`
Information on the runner application. 



**Attributes:**
 
 - <b>`os`</b>:  Operating system to run the runner application on. 
 - <b>`architecture`</b>:  Computer Architecture to run the runner application on. 
 - <b>`download_url`</b>:  URL to download the runner application. 
 - <b>`filename`</b>:  Filename of the runner application. 
 - <b>`temp_download_token`</b>:  A short lived bearer token used to download the  runner, if needed. 
 - <b>`sha256_checksum`</b>:  SHA256 Checksum of the runner application. 





---

<a href="../../github-runner-manager/src/github_runner_manager/types_/github.py#L56"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `SelfHostedRunnerLabel`
A single label of self-hosted runners. 



**Attributes:**
 
 - <b>`id`</b>:  Unique identifier of the label. 
 - <b>`name`</b>:  Name of the label. 
 - <b>`type`</b>:  Type of label. Read-only labels are applied automatically when  the runner is configured. 





---

<a href="../../github-runner-manager/src/github_runner_manager/types_/github.py#L71"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `SelfHostedRunner`
Information on a single self-hosted runner. 



**Attributes:**
 
 - <b>`busy`</b>:  Whether the runner is executing a job. 
 - <b>`id`</b>:  Unique identifier of the runner. 
 - <b>`labels`</b>:  Labels of the runner. 
 - <b>`os`</b>:  Operation system of the runner. 
 - <b>`name`</b>:  Name of the runner. 
 - <b>`status`</b>:  The Github runner status. 





---

<a href="../../github-runner-manager/src/github_runner_manager/types_/github.py#L91"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `SelfHostedRunnerList`
Information on a collection of self-hosted runners. 



**Attributes:**
 
 - <b>`total_count`</b>:  Total number of runners. 
 - <b>`runners`</b>:  List of runners. 





---

<a href="../../github-runner-manager/src/github_runner_manager/types_/github.py#L103"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RegistrationToken`
Token used for registering GitHub runners. 



**Attributes:**
 
 - <b>`token`</b>:  Token for registering GitHub runners. 
 - <b>`expires_at`</b>:  Time the token expires at. 





---

<a href="../../github-runner-manager/src/github_runner_manager/types_/github.py#L115"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RemoveToken`
Token used for removing GitHub runners. 



**Attributes:**
 
 - <b>`token`</b>:  Token for removing GitHub runners. 
 - <b>`expires_at`</b>:  Time the token expires at. 





---

<a href="../../github-runner-manager/src/github_runner_manager/types_/github.py#L127"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `JobConclusion`
Conclusion of a job on GitHub. 

See :https://docs.github.com/en/rest/actions/workflow-runs?apiVersion=2022-11-28#list-workflow-runs-for-a-repository 



**Attributes:**
 
 - <b>`ACTION_REQUIRED`</b>:  Represents additional action required on the job. 
 - <b>`CANCELLED`</b>:  Represents a cancelled job status. 
 - <b>`FAILURE`</b>:  Represents a failed job status. 
 - <b>`NEUTRAL`</b>:  Represents a job status that can optionally succeed or fail. 
 - <b>`SKIPPED`</b>:  Represents a skipped job status. 
 - <b>`SUCCESS`</b>:  Represents a successful job status. 
 - <b>`TIMED_OUT`</b>:  Represents a job that has timed out. 





---

<a href="../../github-runner-manager/src/github_runner_manager/types_/github.py#L152"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `JobStatus`
Status of a job on GitHub. 



**Attributes:**
 
 - <b>`QUEUED`</b>:  Represents a job that is queued. 
 - <b>`IN_PROGRESS`</b>:  Represents a job that is in progress. 
 - <b>`COMPLETED`</b>:  Represents a job that is completed. 
 - <b>`WAITING`</b>:  Represents a job that is waiting. 
 - <b>`REQUESTED`</b>:  Represents a job that is requested. 
 - <b>`PENDING`</b>:  Represents a job that is pending. 





---

<a href="../../github-runner-manager/src/github_runner_manager/types_/github.py#L172"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `JobInfo`
Stats for a job on GitHub. 



**Attributes:**
 
 - <b>`job_id`</b>:  The ID of the job. 
 - <b>`created_at`</b>:  The time the job was created. 
 - <b>`started_at`</b>:  The time the job was started. 
 - <b>`conclusion`</b>:  The end result of a job. 
 - <b>`status`</b>:  The status of the job. 





---

<a href="../../github-runner-manager/src/github_runner_manager/types_/github.py#L190"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `GitHubRepo`
Represent GitHub repository. 



**Attributes:**
 
 - <b>`owner`</b>:  Owner of the GitHub repository. 
 - <b>`repo`</b>:  Name of the GitHub repository. 

<a href="../../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(owner: 'str', repo: 'str') → None
```








---

<a href="../../github-runner-manager/src/github_runner_manager/types_/github.py#L202"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `path`

```python
path() → str
```

Return a string representing the path. 



**Returns:**
  Path to the GitHub entity. 


---

<a href="../../github-runner-manager/src/github_runner_manager/types_/github.py#L211"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `GitHubOrg`
Represent GitHub organization. 



**Attributes:**
 
 - <b>`org`</b>:  Name of the GitHub organization. 
 - <b>`group`</b>:  Runner group to spawn the runners in. 

<a href="../../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(org: 'str', group: 'str') → None
```








---

<a href="../../github-runner-manager/src/github_runner_manager/types_/github.py#L223"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `path`

```python
path() → str
```

Return a string representing the path. 



**Returns:**
  Path to the GitHub entity. 



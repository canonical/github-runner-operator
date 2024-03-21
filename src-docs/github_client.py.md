<!-- markdownlint-disable -->

<a href="../src/github_client.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `github_client.py`
GitHub API client. 

Migrate to PyGithub in the future. PyGithub is still lacking some API such as remove token for runner. 


---

<a href="../src/github_client.py#L38"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `catch_http_errors`

```python
catch_http_errors(
    func: Callable[~ParamT, ~ReturnT]
) → Callable[~ParamT, ~ReturnT]
```

Catch HTTP errors and raise custom exceptions. 



**Args:**
 
 - <b>`func`</b>:  The target function to catch common errors for. 



**Returns:**
 The decorated function. 


---

## <kbd>class</kbd> `GithubClient`
GitHub API client. 

<a href="../src/github_client.py#L80"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(token: str)
```

Instantiate the GiHub API client. 



**Args:**
 
 - <b>`token`</b>:  GitHub personal token for API requests. 




---

<a href="../src/github_client.py#L222"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `delete_runner`

```python
delete_runner(path: GithubOrg | GithubRepo, runner_id: int) → None
```

Delete the self-hosted runner from GitHub. 



**Args:**
 
 - <b>`path`</b>:  GitHub repository path in the format '<owner>/<repo>', or the GitHub organization  name. 
 - <b>`runner_id`</b>:  Id of the runner. 

---

<a href="../src/github_client.py#L243"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_job_info`

```python
get_job_info(
    path: GithubRepo,
    workflow_run_id: str,
    runner_name: str
) → JobStats
```

Get information about a job for a specific workflow run. 



**Args:**
 
 - <b>`path`</b>:  GitHub repository path in the format '<owner>/<repo>'. 
 - <b>`workflow_run_id`</b>:  Id of the workflow run. 
 - <b>`runner_name`</b>:  Name of the runner. 



**Raises:**
 
 - <b>`TokenError`</b>:  if there was an error with the Github token crdential provided. 
 - <b>`JobNotFoundError`</b>:  If no jobs were found. 



**Returns:**
 Job information. 

---

<a href="../src/github_client.py#L89"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_runner_application`

```python
get_runner_application(
    path: GithubOrg | GithubRepo,
    arch: Arch,
    os: str = 'linux'
) → RunnerApplication
```

Get runner application available for download for given arch. 



**Args:**
 
 - <b>`path`</b>:  GitHub repository path in the format '<owner>/<repo>', or the GitHub organization  name. 
 - <b>`arch`</b>:  The runner architecture. 
 - <b>`os`</b>:  The operating system that the runner binary should run on. 



**Raises:**
 
 - <b>`RunnerBinaryError`</b>:  If the runner application for given architecture and OS is not  found. 



**Returns:**
 The runner application. 

---

<a href="../src/github_client.py#L129"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_runner_github_info`

```python
get_runner_github_info(path: GithubOrg | GithubRepo) → list[SelfHostedRunner]
```

Get runner information on GitHub under a repo or org. 



**Args:**
 
 - <b>`path`</b>:  GitHub repository path in the format '<owner>/<repo>', or the GitHub organization  name. 



**Returns:**
 List of runner information. 

---

<a href="../src/github_client.py#L199"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_runner_registration_token`

```python
get_runner_registration_token(path: GithubOrg | GithubRepo) → str
```

Get token from GitHub used for registering runners. 



**Args:**
 
 - <b>`path`</b>:  GitHub repository path in the format '<owner>/<repo>', or the GitHub organization  name. 



**Returns:**
 The registration token. 

---

<a href="../src/github_client.py#L177"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_runner_remove_token`

```python
get_runner_remove_token(path: GithubOrg | GithubRepo) → str
```

Get token from GitHub used for removing runners. 



**Args:**
 
 - <b>`path`</b>:  The Github org/repo path. 



**Returns:**
 The removing token. 



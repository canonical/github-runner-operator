<!-- markdownlint-disable -->

<a href="../src/github_client.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `github_client.py`
GitHub API client. 

Migrate to PyGithub in the future. PyGithub is still lacking some API such as remove token for runner. 



---

## <kbd>class</kbd> `GithubClient`
GitHub API client. 




---

<a href="../.tox/src-docs/lib/python3.10/site-packages/github_runner_manager/github_client.py#L36"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_runner_application`

```python
get_runner_application(
    path: GitHubOrg | GitHubRepo,
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



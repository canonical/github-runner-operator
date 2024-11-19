<!-- markdownlint-disable -->

<a href="../src/github_runner_manager/repo_policy_compliance_client.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `repo_policy_compliance_client`
Client for requesting repo policy compliance service. 



---

<a href="../src/github_runner_manager/repo_policy_compliance_client.py#L16"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RepoPolicyComplianceClient`
Client for repo policy compliance service. 



**Attributes:**
 
 - <b>`base_url`</b>:  Base url to the repo policy compliance service. 
 - <b>`token`</b>:  Charm token configured for the repo policy compliance service. 

<a href="../src/github_runner_manager/repo_policy_compliance_client.py#L24"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(url: str, charm_token: str) → None
```

Construct the RepoPolicyComplianceClient. 



**Args:**
 
 - <b>`url`</b>:  Base URL to the repo policy compliance service. 
 - <b>`charm_token`</b>:  Charm token configured for the repo policy compliance service. 




---

<a href="../src/github_runner_manager/repo_policy_compliance_client.py#L35"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_one_time_token`

```python
get_one_time_token() → str
```

Get a single-use token for repo policy compliance check. 



**Raises:**
 
 - <b>`HTTPError`</b>:  If there was an error getting one-time token from repo-policy-compliance                 service. 



**Returns:**
 The one-time token to be used in a single request of repo policy compliance check. 



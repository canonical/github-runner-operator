<!-- markdownlint-disable -->

<a href="../src/repo_policy_compliance_client.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `repo_policy_compliance_client.py`
Client for requesting repo policy compliance service. 



---

## <kbd>class</kbd> `RepoPolicyComplianceClient`
Client for repo policy compliance service. 



**Attributes:**
 
 - <b>`base_url`</b>:  Base url to the repo policy compliance service. 
 - <b>`token`</b>:  Charm token configured for the repo policy compliance service. 

<a href="../src/repo_policy_compliance_client.py#L23"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(session: Session, url: str, charm_token: str) → None
```

Construct the RepoPolicyComplianceClient. 



**Args:**
 
 - <b>`session`</b>:  The request Session object for making HTTP requests. 
 - <b>`url`</b>:  Base URL to the repo policy compliance service. 
 - <b>`charm_token`</b>:  Charm token configured for the repo policy compliance service. 




---

<a href="../src/repo_policy_compliance_client.py#L35"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_one_time_token`

```python
get_one_time_token() → str
```

Get a single-use token for repo policy compliance check. 



**Returns:**
  The one-time token to be used in a single request of repo policy compliance check. 



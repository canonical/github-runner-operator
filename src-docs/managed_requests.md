<!-- markdownlint-disable -->

<a href="../src/apis/managed_requests.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `managed_requests`
Get configured requests session instance 


---

<a href="../src/apis/managed_requests.py#L10"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `get_requests_session`

```python
get_requests_session(proxy: ProxyConfig) → Session
```

Get managed requests session instance. 



**Args:**
 
 - <b>`proxy`</b>:  HTTP proxy configurations. 



**Returns:**
 Requests session with proxy and retry setup. 



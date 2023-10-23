<!-- markdownlint-disable -->

<a href="../src/charm_state.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `charm_state.py`
State of the Charm. 

**Global Variables**
---------------
- **COS_AGENT_INTEGRATION_NAME**


---

## <kbd>class</kbd> `State`
The charm state. 



**Attributes:**
 
 - <b>`proxy_config`</b>:  Proxy configuration. 
 - <b>`_charm`</b>:  The charm instance. 




---

<a href="../src/charm_state.py#L27"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(charm: CharmBase) → State
```

Initialize the state from charm. 



**Returns:**
  Current state of the charm. 



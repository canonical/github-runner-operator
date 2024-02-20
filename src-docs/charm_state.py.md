<!-- markdownlint-disable -->

<a href="../src/charm_state.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `charm_state.py`
State of the Charm. 

**Global Variables**
---------------
- **ARCHITECTURES_ARM64**
- **ARCHITECTURES_X86**
- **OPENSTACK_CLOUDS_YAML_CONFIG_NAME**
- **COS_AGENT_INTEGRATION_NAME**
- **DEBUG_SSH_INTEGRATION_NAME**


---

## <kbd>class</kbd> `ARCH`
Supported system architectures. 





---

## <kbd>class</kbd> `CharmConfig`
Charm configuration. 



**Attributes:**
 
 - <b>`runner_storage`</b>:  Storage to be used as disk for the runner. 




---

<a href="../src/charm_state.py#L78"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(charm: CharmBase) → CharmConfig
```

Initialize the config from charm. 



**Args:**
 
 - <b>`charm`</b>:  The charm instance. 



**Returns:**
 Current config of the charm. 


---

## <kbd>class</kbd> `CharmConfigInvalidError`
Raised when charm config is invalid. 



**Attributes:**
 
 - <b>`msg`</b>:  Explanation of the error. 

<a href="../src/charm_state.py#L59"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str)
```

Initialize a new instance of the CharmConfigInvalidError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 





---

## <kbd>class</kbd> `ProxyConfig`
Proxy configuration. 



**Attributes:**
 
 - <b>`http_proxy`</b>:  HTTP proxy address. 
 - <b>`https_proxy`</b>:  HTTPS proxy address. 
 - <b>`no_proxy`</b>:  Comma-separated list of hosts that should not be proxied. 
 - <b>`use_aproxy`</b>:  Whether aproxy should be used. 


---

#### <kbd>property</kbd> aproxy_address

Return the aproxy address. 



---

<a href="../src/charm_state.py#L169"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `check_fields`

```python
check_fields(values: dict) → dict
```

Validate the proxy configuration. 

---

<a href="../src/charm_state.py#L135"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(charm: CharmBase) → ProxyConfig
```

Initialize the proxy config from charm. 



**Args:**
 
 - <b>`charm`</b>:  The charm instance. 



**Returns:**
 Current proxy config of the charm. 


---

## <kbd>class</kbd> `RunnerStorage`
Supported storage as runner disk. 





---

## <kbd>class</kbd> `SSHDebugConnection`
SSH connection information for debug workflow. 



**Attributes:**
 
 - <b>`host`</b>:  The SSH relay server host IP address inside the VPN. 
 - <b>`port`</b>:  The SSH relay server port. 
 - <b>`rsa_fingerprint`</b>:  The host SSH server public RSA key fingerprint. 
 - <b>`ed25519_fingerprint`</b>:  The host SSH server public ed25519 key fingerprint. 




---

<a href="../src/charm_state.py#L231"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(charm: CharmBase) → list['SSHDebugConnection']
```

Initialize the SSHDebugInfo from charm relation data. 



**Args:**
 
 - <b>`charm`</b>:  The charm instance. 


---

## <kbd>class</kbd> `State`
The charm state. 



**Attributes:**
 
 - <b>`arch`</b>:  The underlying compute architecture, i.e. x86_64, amd64, arm64/aarch64. 
 - <b>`charm_config`</b>:  Configuration of the juju charm. 
 - <b>`is_metrics_logging_available`</b>:  Whether the charm is able to issue metrics. 
 - <b>`openstack_clouds_yaml`</b>:  The openstack clouds.yaml configuration. 
 - <b>`proxy_config`</b>:  Proxy-related configuration. 
 - <b>`ssh_debug_connections`</b>:  SSH debug connections configuration information. 




---

<a href="../src/charm_state.py#L284"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(charm: CharmBase) → State
```

Initialize the state from charm. 



**Args:**
 
 - <b>`charm`</b>:  The charm instance. 



**Returns:**
 Current state of the charm. 


---

## <kbd>class</kbd> `UnsupportedArchitectureError`
Raised when given machine charm architecture is unsupported. 



**Attributes:**
 
 - <b>`arch`</b>:  The current machine architecture. 

<a href="../src/charm_state.py#L188"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(arch: str) → None
```

Initialize a new instance of the CharmConfigInvalidError exception. 



**Args:**
 
 - <b>`arch`</b>:  The current machine architecture. 






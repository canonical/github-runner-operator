<!-- markdownlint-disable -->

<a href="../src/charm_state.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `charm_state.py`
State of the Charm. 



---

## <kbd>class</kbd> `LokiEndpoint`
Information about the Loki endpoint. 

Attrs:  url: The URL of the Loki endpoint. 


---

#### <kbd>property</kbd> model_computed_fields

Get the computed fields of this model instance. 



**Returns:**
  A dictionary of computed field names and their corresponding `ComputedFieldInfo` objects. 

---

#### <kbd>property</kbd> model_extra

Get extra fields set during validation. 



**Returns:**
  A dictionary of extra fields, or `None` if `config.extra` is not set to `"allow"`. 

---

#### <kbd>property</kbd> model_fields_set

Returns the set of fields that have been set on this model instance. 



**Returns:**
  A set of strings representing the fields that have been set,  i.e. that were not filled from defaults. 




---

## <kbd>class</kbd> `ProxyConfig`
Represent HTTP-related proxy settings. 



**Attributes:**
 
 - <b>`http_proxy`</b>:  The http proxy URL. 
 - <b>`https_proxy`</b>:  The https proxy URL. 
 - <b>`no_proxy`</b>:  Comma separated list of hostnames to bypass proxy. 


---

#### <kbd>property</kbd> model_computed_fields

Get the computed fields of this model instance. 



**Returns:**
  A dictionary of computed field names and their corresponding `ComputedFieldInfo` objects. 

---

#### <kbd>property</kbd> model_extra

Get extra fields set during validation. 



**Returns:**
  A dictionary of extra fields, or `None` if `config.extra` is not set to `"allow"`. 

---

#### <kbd>property</kbd> model_fields_set

Returns the set of fields that have been set on this model instance. 



**Returns:**
  A set of strings representing the fields that have been set,  i.e. that were not filled from defaults. 



---

<a href="../src/charm_state.py#L31"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_env`

```python
from_env() → ProxyConfig
```

Instantiate ProxyConfig from juju charm environment. 



**Returns:**
  The proxy configuration. 


---

## <kbd>class</kbd> `State`
The charm state. 

Attrs:  proxy_config: Proxy configuration.  loki_push_api_consumer:  The consumer which provides the Loki Endpoints from integration data. 


---

#### <kbd>property</kbd> is_metrics_logging_available

Return whether metric logging is available. 



**Returns:**
  True if metric logging is available, False otherwise. 

---

#### <kbd>property</kbd> loki_endpoint

Return a Loki endpoint. 



**Returns:**
  A Loki endpoint if available, None otherwise. 



**Raises:**
 
 - <b>`pydantic.ValidationError`</b>:  If one of the Loki endpoints is invalid, as this is a sign of a corrupt integration. 



---

<a href="../src/charm_state.py#L99"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(loki_consumer: LokiPushApiConsumer) → State
```

Initialize the state from charm. 



**Returns:**
  Current state of the charm. 



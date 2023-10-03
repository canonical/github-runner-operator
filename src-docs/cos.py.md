<!-- markdownlint-disable -->

<a href="../src/cos.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `cos.py`
The COS integration observer. 

**Global Variables**
---------------
- **METRICS_LOGGING_INTEGRATION_NAME**
- **PROMTAIL_HEALTH_CHECK_INTERVAL_MINUTES**


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

## <kbd>class</kbd> `LokiIntegrationData`
Represents Loki integration data. 

Attrs:  endpoints: The Loki endpoints.  promtail_binaries: The Promtail binaries. 


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

## <kbd>class</kbd> `LokiIntegrationDataIncompleteError`
Indicates an error if the Loki integration data is not complete for Promtail startup. 

<a href="../src/cos.py#L69"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str)
```

Initialize a new instance of the LokiIntegrationDataNotComplete exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 





---

## <kbd>class</kbd> `Observer`
COS integration observer. 

<a href="../src/cos.py#L89"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(charm: CharmBase, state: State)
```

Initialize the COS observer and register event handlers. 



**Args:**
 
 - <b>`charm`</b>:  The parent charm to attach the observer to. 
 - <b>`state`</b>:  The charm state. 


---

#### <kbd>property</kbd> model

Shortcut for more simple access the model. 



---

<a href="../src/cos.py#L161"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `metrics_logging_available`

```python
metrics_logging_available() → bool
```

Check that the metrics logging integration is set up correctly. 



**Returns:**
  True if the integration is established, False otherwise. 


---

## <kbd>class</kbd> `PromtailBinary`
Information about the Promtail binary. 

Attrs:  url: The URL to download the Promtail binary from.  zipsha: The SHA256 hash of the Promtail zip file.  binsha: The SHA256 hash of the Promtail binary. 


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

## <kbd>class</kbd> `PromtailHealthCheckEvent`
Event representing a periodic check to ensure Promtail is running. 





---

## <kbd>class</kbd> `PromtailNotRunningError`
Indicates an error if Promtail is not running. 






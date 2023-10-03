<!-- markdownlint-disable -->

<a href="../src/metrics.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `metrics.py`
Models and functions for the metric events. 

**Global Variables**
---------------
- **PROMTAIL_PUSH_API_URL**

---

<a href="../src/metrics.py#L70"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `issue_event`

```python
issue_event(event: Event) → None
```

Transmit an event to Promtail. 



**Args:**
 
 - <b>`event`</b>:  The metric event to log. 

**Raises:**
 
 - <b>`requests.HTTPError`</b>:  If the HTTP request to Promtail fails. 


---

## <kbd>class</kbd> `Event`
Base class for metric events. 

Attrs:  timestamp: The UNIX time stamp of the time at which the event was originally issued. 


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

## <kbd>class</kbd> `RunnerInstalled`
Metric event for when a runner is installed. 

Attrs:  flavor: Describes the characteristics of the runner.  The flavour could be for example "small".  duration: The duration of the installation in seconds. 


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





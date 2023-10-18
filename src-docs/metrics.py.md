<!-- markdownlint-disable -->

<a href="../src/metrics.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `metrics.py`
Models and functions for the metric events. 

**Global Variables**
---------------
- **LOG_ROTATE_TIMER_SYSTEMD_SERVICE**
- **SYSTEMCTL_PATH**

---

<a href="../src/metrics.py#L79"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `issue_event`

```python
issue_event(event: Event) → None
```

Issue a metric event. 

The metric event is logged to the metrics log. 



**Args:**
 
 - <b>`event`</b>:  The metric event to log. 

**Raises:**
 
 - <b>`OSError`</b>:  If an error occurs while writing the metrics log. 


---

<a href="../src/metrics.py#L126"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `setup_logrotate`

```python
setup_logrotate()
```

Configure logrotate for the metrics log. 



**Raises:**
 
 - <b>`LogrotateSetupError`</b>:  If the logrotate.timer cannot be enabled. 


---

## <kbd>class</kbd> `Event`
Base class for metric events. 

Attrs:  timestamp: The UNIX time stamp of the time at which the event was originally issued.  event: The name of the event. Will be set to the class name in snake case if not provided. 

<a href="../src/metrics.py#L52"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(*args, **kwargs)
```

Initialize the event. 



**Args:**
 
 - <b>`*args`</b>:  The positional arguments to pass to the base class. 
 - <b>`**kwargs`</b>:  The keyword arguments to pass to the base class. These are used to set the  specific fields. E.g. timestamp=12345 will set the timestamp field to 12345. 





---

## <kbd>class</kbd> `RunnerInstalled`
Metric event for when a runner is installed. 

Attrs:  flavor: Describes the characteristics of the runner.  The flavour could be for example "small".  duration: The duration of the installation in seconds. 

<a href="../src/metrics.py#L52"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(*args, **kwargs)
```

Initialize the event. 



**Args:**
 
 - <b>`*args`</b>:  The positional arguments to pass to the base class. 
 - <b>`**kwargs`</b>:  The keyword arguments to pass to the base class. These are used to set the  specific fields. E.g. timestamp=12345 will set the timestamp field to 12345. 






<!-- markdownlint-disable -->

<a href="../src/metrics.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `metrics.py`
Models and functions for the metric events. 

**Global Variables**
---------------
- **LOG_ROTATE_TIMER_SYSTEMD_SERVICE**
- **SYSTEMCTL_PATH**

---

<a href="../src/metrics.py#L98"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `issue_event`

```python
issue_event(event: Event) → None
```

Issue a metric event. 

The metric event is logged to the metrics log. 



**Args:**
 
 - <b>`event`</b>:  The metric event to log. 



**Raises:**
 
 - <b>`IssueMetricEventError`</b>:  If the event cannot be logged. 


---

<a href="../src/metrics.py#L149"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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



**Attributes:**
 
 - <b>`timestamp`</b>:  The UNIX time stamp of the time at which the event was originally issued. 
 - <b>`event`</b>:  The name of the event. Will be set to the class name in snake case if not provided. 

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



**Attributes:**
 
 - <b>`flavor`</b>:  Describes the characteristics of the runner.  The flavor could be for example "small". 
 - <b>`duration`</b>:  The duration of the installation in seconds. 

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

## <kbd>class</kbd> `RunnerStart`
Metric event for when a runner is started. 



**Attributes:**
 
 - <b>`flavor`</b>:  Describes the characteristics of the runner.  The flavor could be for example "small". 
 - <b>`workflow`</b>:  The workflow name. 
 - <b>`repo`</b>:  The repository name. 
 - <b>`github_event`</b>:  The github event. 
 - <b>`idle`</b>:  The idle time in seconds. 

<a href="../src/metrics.py#L52"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(*args, **kwargs)
```

Initialize the event. 



**Args:**
 
 - <b>`*args`</b>:  The positional arguments to pass to the base class. 
 - <b>`**kwargs`</b>:  The keyword arguments to pass to the base class. These are used to set the  specific fields. E.g. timestamp=12345 will set the timestamp field to 12345. 






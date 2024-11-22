<!-- markdownlint-disable -->

<a href="../src/github_runner_manager/metrics/events.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `metrics.events`
Models and functions for the metric events. 


---

<a href="../src/github_runner_manager/metrics/events.py#L157"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/github_runner_manager/metrics/events.py#L19"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `Event`
Base class for metric events. 



**Attributes:**
 
 - <b>`timestamp`</b>:  The UNIX time stamp of the time at which the event was originally issued. 
 - <b>`event`</b>:  The name of the event. Will be set to the class name in snake case if not provided. 

<a href="../src/github_runner_manager/metrics/events.py#L48"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(*args: Any, **kwargs: Any)
```

Initialize the event. 



**Args:**
 
 - <b>`args`</b>:  The positional arguments to pass to the base class. 
 - <b>`kwargs`</b>:  The keyword arguments to pass to the base class. These are used to set the  specific fields. E.g. timestamp=12345 will set the timestamp field to 12345. 





---

<a href="../src/github_runner_manager/metrics/events.py#L62"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerInstalled`
Metric event for when a runner is installed. 



**Attributes:**
 
 - <b>`flavor`</b>:  Describes the characteristics of the runner.  The flavor could be for example "small". 
 - <b>`duration`</b>:  The duration of the installation in seconds. 

<a href="../src/github_runner_manager/metrics/events.py#L48"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(*args: Any, **kwargs: Any)
```

Initialize the event. 



**Args:**
 
 - <b>`args`</b>:  The positional arguments to pass to the base class. 
 - <b>`kwargs`</b>:  The keyword arguments to pass to the base class. These are used to set the  specific fields. E.g. timestamp=12345 will set the timestamp field to 12345. 





---

<a href="../src/github_runner_manager/metrics/events.py#L75"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerStart`
Metric event for when a runner is started. 



**Attributes:**
 
 - <b>`flavor`</b>:  Describes the characteristics of the runner.  The flavor could be for example "small". 
 - <b>`workflow`</b>:  The workflow name. 
 - <b>`repo`</b>:  The repository name. 
 - <b>`github_event`</b>:  The github event. 
 - <b>`idle`</b>:  The idle time in seconds. 
 - <b>`queue_duration`</b>:  The time in seconds it took before the runner picked up the job.  This is optional as we rely on the Github API and there may be problems  retrieving the data. 

<a href="../src/github_runner_manager/metrics/events.py#L48"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(*args: Any, **kwargs: Any)
```

Initialize the event. 



**Args:**
 
 - <b>`args`</b>:  The positional arguments to pass to the base class. 
 - <b>`kwargs`</b>:  The keyword arguments to pass to the base class. These are used to set the  specific fields. E.g. timestamp=12345 will set the timestamp field to 12345. 





---

<a href="../src/github_runner_manager/metrics/events.py#L98"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `CodeInformation`
Information about a status code. 

This could e.g. be an exit code or a http status code. 



**Attributes:**
 
 - <b>`code`</b>:  The status code. 





---

<a href="../src/github_runner_manager/metrics/events.py#L110"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerStop`
Metric event for when a runner is stopped. 



**Attributes:**
 
 - <b>`flavor`</b>:  Describes the characteristics of the runner.  The flavor could be for example "small". 
 - <b>`workflow`</b>:  The workflow name. 
 - <b>`repo`</b>:  The repository name. 
 - <b>`github_event`</b>:  The github event. 
 - <b>`status`</b>:  A string describing the reason for stopping the runner. 
 - <b>`status_info`</b>:  More information about the status. 
 - <b>`job_duration`</b>:  The duration of the job in seconds. 
 - <b>`job_conclusion`</b>:  The job conclusion, e.g. "success", "failure", ... 

<a href="../src/github_runner_manager/metrics/events.py#L48"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(*args: Any, **kwargs: Any)
```

Initialize the event. 



**Args:**
 
 - <b>`args`</b>:  The positional arguments to pass to the base class. 
 - <b>`kwargs`</b>:  The keyword arguments to pass to the base class. These are used to set the  specific fields. E.g. timestamp=12345 will set the timestamp field to 12345. 





---

<a href="../src/github_runner_manager/metrics/events.py#L135"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `Reconciliation`
Metric event for when the charm has finished reconciliation. 



**Attributes:**
 
 - <b>`flavor`</b>:  Describes the characteristics of the runner.  The flavor could be for example "small". 
 - <b>`crashed_runners`</b>:  The number of crashed runners. 
 - <b>`idle_runners`</b>:  The number of idle runners. 
 - <b>`active_runners`</b>:  The number of active runners. 
 - <b>`expected_runners`</b>:  The expected number of runners. This is optional as it is not suitable  for reactive runners. 
 - <b>`duration`</b>:  The duration of the reconciliation in seconds. 

<a href="../src/github_runner_manager/metrics/events.py#L48"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(*args: Any, **kwargs: Any)
```

Initialize the event. 



**Args:**
 
 - <b>`args`</b>:  The positional arguments to pass to the base class. 
 - <b>`kwargs`</b>:  The keyword arguments to pass to the base class. These are used to set the  specific fields. E.g. timestamp=12345 will set the timestamp field to 12345. 






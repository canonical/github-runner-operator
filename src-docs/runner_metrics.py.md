<!-- markdownlint-disable -->

<a href="../src/runner_metrics.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `runner_metrics.py`
Classes and function to extract the metrics from a shared filesystem. 

**Global Variables**
---------------
- **FILE_SIZE_BYTES_LIMIT**
- **PRE_JOB_METRICS_FILE_NAME**
- **POST_JOB_METRICS_FILE_NAME**
- **RUNNER_INSTALLED_TS_FILE_NAME**

---

<a href="../src/runner_metrics.py#L215"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `extract`

```python
extract(ignore_runners: set[str]) → Iterator[RunnerMetrics]
```

Extract metrics from runners. 

The metrics are extracted from the shared filesystem of given runners. Orphan shared filesystems are cleaned up. 

If corrupt data is found, the metrics are not processed further and the filesystem is moved to a special quarantine directory, as this may indicate that a malicious runner is trying to manipulate the shared file system. 

In order to avoid DoS attacks, the file size is also checked. 



**Args:**
 
 - <b>`ignore_runners`</b>:  The set of runners to ignore. 



**Returns:**
 An iterator over the extracted metrics. 


---

<a href="../src/runner_metrics.py#L242"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `issue_events`

```python
issue_events(
    runner_metrics: RunnerMetrics,
    flavor: str,
    queue_duration: Optional[float]
) → set[Type[Event]]
```

Issue the metrics events for a runner. 



**Args:**
 
 - <b>`runner_metrics`</b>:  The metrics for the runner. 
 - <b>`flavor`</b>:  The flavor of the runner. 
 - <b>`queue_duration`</b>:  The queue duration of the runner. 



**Returns:**
 A set of issued events. 


---

## <kbd>class</kbd> `PostJobMetrics`
Metrics for the post-job phase of a runner. 



**Args:**
 
 - <b>`timestamp`</b>:  The UNIX time stamp of the time at which the event was originally issued. 
 - <b>`status`</b>:  The status of the job. 





---

## <kbd>class</kbd> `PostJobStatus`
The status of the post-job phase of a runner. 





---

## <kbd>class</kbd> `PreJobMetrics`
Metrics for the pre-job phase of a runner. 



**Args:**
 
 - <b>`timestamp`</b>:  The UNIX time stamp of the time at which the event was originally issued. 
 - <b>`workflow`</b>:  The workflow name. 
 - <b>`workflow_run_id`</b>:  The workflow run id. 
 - <b>`repository`</b>:  The repository name. 
 - <b>`event`</b>:  The github event. 





---

## <kbd>class</kbd> `RunnerMetrics`
Metrics for a runner. 



**Args:**
 
 - <b>`installed_timestamp`</b>:  The UNIX time stamp of the time at which the runner was installed. 
 - <b>`pre_job`</b>:  The metrics for the pre-job phase. 
 - <b>`post_job`</b>:  The metrics for the post-job phase. 
 - <b>`runner_name`</b>:  The name of the runner. 






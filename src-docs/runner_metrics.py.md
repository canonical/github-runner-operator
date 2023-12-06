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

<a href="../src/runner_metrics.py#L242"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `extract`

```python
extract(flavor: str, ignore_runners: set[str]) → dict[Type[Event], int]
```

Extract and issue metrics from runners. 

The metrics are extracted from the shared filesystem of given runners and respective metric events are issued. Orphan shared filesystems are cleaned up. 

If corrupt data is found, an error is raised immediately, as this may indicate that a malicious runner is trying to manipulate the shared file system. In order to avoid DoS attacks, the file size is also checked. 



**Args:**
 
 - <b>`flavor`</b>:  The flavor of the runners to extract metrics from. 
 - <b>`ignore_runners`</b>:  The set of runners to ignore. 



**Returns:**
 A dictionary containing the number of issued events per event type. 


---

## <kbd>class</kbd> `PostJobMetrics`
Metrics for the post-job phase of a runner. 



**Args:**
 
 - <b>`timestamp`</b>:  The UNIX time stamp of the time at which the event was originally issued. 
 - <b>`status`</b>:  The status of the job. 
 - <b>`status_info`</b>:  More information about the status. 





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

## <kbd>class</kbd> `ReturnCodeInformation`
Information about the return code of the post-job phase of a runner. 



**Attributes:**
 
 - <b>`code`</b>:  The exit code of the runner. 





---

## <kbd>class</kbd> `RunnerMetrics`
Metrics for a runner. 



**Args:**
 
 - <b>`installed_timestamp`</b>:  The UNIX time stamp of the time at which the runner was installed. 
 - <b>`pre_job`</b>:  The metrics for the pre-job phase. 
 - <b>`post_job`</b>:  The metrics for the post-job phase. 






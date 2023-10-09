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

<a href="../src/runner_metrics.py#L174"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `extract`

```python
extract(flavor: str, ignore_runners: set[str]) → None
```

Extract and issue metrics from runners. 

The metrics are extracted from the shared filesystem of given runners and issued to Promtail. Orphan shared filesystems are cleaned up. 

If corrupt data is found, an error is raised immediately, as this may indicate that a malicious runner is trying to manipulate the shared file system. In order to avoid DoS attacks, the file size is also checked. 



**Args:**
 
 - <b>`flavor`</b>:  The flavour of the runners to extract metrics from. 
 - <b>`ignore_runners`</b>:  The set of runners to ignore. 



**Raises:**
 
 - <b>`JSONDecodeError`</b>:  If one of the JSON files inside a shared filesystem does  not contain valid JSON. 
 - <b>`pydantic.ValidationError`</b>:  If one of the files inside a shared filesystem is not valid. 
 - <b>`FileSizeTooLargeError`</b>:  If one of the files is too large. 
 - <b>`FileNotFoundError`</b>:  If installed_timestamp is not found inside a shared filesystem. 


---

## <kbd>class</kbd> `FileSizeTooLargeError`
Represents an error with the file size being too large. 

<a href="../src/runner_metrics.py#L26"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str)
```

Initialize a new instance of the FileSizeTooLargeError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 





---

## <kbd>class</kbd> `PostJobMetrics`
Metrics for the post-job phase of a runner. 



**Args:**
 
 - <b>`timestamp`</b>:  The UNIX time stamp of the time at which the event was originally issued. 
 - <b>`status`</b>:  The status of the job. 





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






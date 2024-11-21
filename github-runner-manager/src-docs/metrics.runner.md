<!-- markdownlint-disable -->

<a href="../src/github_runner_manager/metrics/runner.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `metrics.runner`
Classes and function to extract the metrics from storage and issue runner metrics events. 

**Global Variables**
---------------
- **FILE_SIZE_BYTES_LIMIT**
- **PRE_JOB_METRICS_FILE_NAME**
- **POST_JOB_METRICS_FILE_NAME**
- **RUNNER_INSTALLATION_START_TS_FILE_NAME**
- **RUNNER_INSTALLED_TS_FILE_NAME**

---

<a href="../src/github_runner_manager/metrics/runner.py#L110"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `extract`

```python
extract(
    metrics_storage_manager: StorageManagerProtocol,
    runners: set[str],
    include: bool = False
) → Iterator[RunnerMetrics]
```

Extract metrics from runners. 

The metrics are extracted from the metrics storage of the runners. Orphan storages are cleaned up. 

If corrupt data is found, the metrics are not processed further and the storage is moved to a special quarantine directory, as this may indicate that a malicious runner is trying to manipulate the files on the storage. 

In order to avoid DoS attacks, the file size is also checked. 



**Args:**
 
 - <b>`metrics_storage_manager`</b>:  The metrics storage manager. 
 - <b>`runners`</b>:  The runners to include or exclude. 
 - <b>`include`</b>:  If true the provided runners are included for metric extraction, else the provided  runners are excluded. 



**Yields:**
 Extracted runner metrics of a particular runner. 


---

<a href="../src/github_runner_manager/metrics/runner.py#L146"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `issue_events`

```python
issue_events(
    runner_metrics: RunnerMetrics,
    flavor: str,
    job_metrics: Optional[GithubJobMetrics]
) → set[Type[Event]]
```

Issue the metrics events for a runner. 



**Args:**
 
 - <b>`runner_metrics`</b>:  The metrics for the runner. 
 - <b>`flavor`</b>:  The flavor of the runner. 
 - <b>`job_metrics`</b>:  The metrics about the job run by the runner. 



**Returns:**
 A set of issued events. 


---

<a href="../src/github_runner_manager/metrics/runner.py#L35"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `PreJobMetrics`
Metrics for the pre-job phase of a runner. 



**Attributes:**
 
 - <b>`timestamp`</b>:  The UNIX time stamp of the time at which the event was originally issued. 
 - <b>`workflow`</b>:  The workflow name. 
 - <b>`workflow_run_id`</b>:  The workflow run id. 
 - <b>`repository`</b>:  The repository path in the format '<owner>/<repo>'. 
 - <b>`event`</b>:  The github event. 





---

<a href="../src/github_runner_manager/metrics/runner.py#L53"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `PostJobStatus`
The status of the post-job phase of a runner. 



**Attributes:**
 
 - <b>`NORMAL`</b>:  Represents a normal post-job. 
 - <b>`ABNORMAL`</b>:  Represents an error with post-job. 
 - <b>`REPO_POLICY_CHECK_FAILURE`</b>:  Represents an error with repo-policy-compliance check. 





---

<a href="../src/github_runner_manager/metrics/runner.py#L67"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `CodeInformation`
Information about a status code. 



**Attributes:**
 
 - <b>`code`</b>:  The status code. 





---

<a href="../src/github_runner_manager/metrics/runner.py#L77"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `PostJobMetrics`
Metrics for the post-job phase of a runner. 



**Attributes:**
 
 - <b>`timestamp`</b>:  The UNIX time stamp of the time at which the event was originally issued. 
 - <b>`status`</b>:  The status of the job. 
 - <b>`status_info`</b>:  More information about the status. 





---

<a href="../src/github_runner_manager/metrics/runner.py#L91"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerMetrics`
Metrics for a runner. 



**Attributes:**
 
 - <b>`installation_start_timestamp`</b>:  The UNIX time stamp of the time at which the runner  installation started. 
 - <b>`installed_timestamp`</b>:  The UNIX time stamp of the time at which the runner was installed. 
 - <b>`pre_job`</b>:  The metrics for the pre-job phase. 
 - <b>`post_job`</b>:  The metrics for the post-job phase. 
 - <b>`runner_name`</b>:  The name of the runner. 






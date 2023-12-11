<!-- markdownlint-disable -->

<a href="../src/github_metrics.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `github_metrics.py`
Functions to calculate metrics from data retrieved from GitHub. 


---

<a href="../src/github_metrics.py#L11"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `job_queue_duration`

```python
job_queue_duration(
    github_client: GithubClient,
    pre_job_metrics: PreJobMetrics,
    runner_name: str
) → float
```

Calculate the job queue duration. 

The Github API is accessed to retrieve the job data for the runner, which includes the time the job was created and the time the job was started. 



**Args:**
 
 - <b>`ghapi`</b>:  The GitHub API client. 
 - <b>`pre_job_metrics`</b>:  The pre-job metrics. 
 - <b>`runner_name`</b>:  The name of the runner. 



**Returns:**
 The time in seconds the job took before the runner picked it up. 



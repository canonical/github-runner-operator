<!-- markdownlint-disable -->

<a href="../src/metrics/github.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `metrics.github`
Functions to calculate metrics from data retrieved from GitHub. 


---

<a href="../src/metrics/github.py#L16"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `job`

```python
job(
    github_client: GithubClient,
    pre_job_metrics: PreJobMetrics,
    runner_name: str
) → GithubJobMetrics
```

Calculate the job metrics for a runner. 

The Github API is accessed to retrieve the job data for the runner. 



**Args:**
 
 - <b>`github_client`</b>:  The GitHub API client. 
 - <b>`pre_job_metrics`</b>:  The pre-job metrics. 
 - <b>`runner_name`</b>:  The name of the runner. 



**Raises:**
 
 - <b>`GithubMetricsError`</b>:  If the job for given workflow run is not found. 



**Returns:**
 The job metrics. 



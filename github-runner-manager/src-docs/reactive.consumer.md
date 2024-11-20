<!-- markdownlint-disable -->

<a href="../src/github_runner_manager/reactive/consumer.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `reactive.consumer`
Module responsible for consuming jobs from the message queue. 


---

<a href="../src/github_runner_manager/reactive/consumer.py#L80"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `get_queue_size`

```python
get_queue_size(queue_config: QueueConfig) → int
```

Get the size of the message queue. 



**Args:**
 
 - <b>`queue_config`</b>:  The configuration for the message queue. 



**Returns:**
 The size of the queue. 



**Raises:**
 
 - <b>`QueueError`</b>:  If an error when communicating with the queue occurs. 


---

<a href="../src/github_runner_manager/reactive/consumer.py#L100"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `consume`

```python
consume(
    queue_config: QueueConfig,
    runner_manager: RunnerManager,
    github_client: GithubClient,
    supported_labels: set[str]
) → None
```

Consume a job from the message queue. 

Log the job details and acknowledge the message. If the job details are invalid, reject the message and raise an error. 



**Args:**
 
 - <b>`queue_config`</b>:  The configuration for the message queue. 
 - <b>`runner_manager`</b>:  The runner manager used to create the runner. 
 - <b>`github_client`</b>:  The GitHub client to use to check the job status. 
 - <b>`supported_labels`</b>:  The supported labels for the runner. If the job has unsupported labels,  the message is requeued. 



**Raises:**
 
 - <b>`JobError`</b>:  If the job details are invalid. 
 - <b>`QueueError`</b>:  If an error when communicating with the queue occurs. 


---

<a href="../reactive/consumer/signal_handler#L234"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `signal_handler`

```python
signal_handler(signal_code: Signals) → Generator[NoneType, NoneType, NoneType]
```

Set a signal handler and after the context, restore the default handler. 

The signal handler exits the process. 



**Args:**
 
 - <b>`signal_code`</b>:  The signal code to handle. 


---

<a href="../src/github_runner_manager/reactive/consumer.py#L30"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `JobPickedUpStates`
The states of a job that indicate it has been picked up. 



**Attributes:**
 
 - <b>`COMPLETED`</b>:  The job has completed. 
 - <b>`IN_PROGRESS`</b>:  The job is in progress. 





---

<a href="../src/github_runner_manager/reactive/consumer.py#L42"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `JobDetails`
A class to translate the payload. 



**Attributes:**
 
 - <b>`labels`</b>:  The labels of the job. 
 - <b>`url`</b>:  The URL of the job to check its status. 




---

<a href="../src/github_runner_manager/reactive/consumer.py#L53"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `check_job_url_path_is_not_empty`

```python
check_job_url_path_is_not_empty(v: HttpUrl) → HttpUrl
```

Check that the job_url path is not empty. 



**Args:**
 
 - <b>`v`</b>:  The job_url to check. 



**Returns:**
 The job_url if it is valid. 



**Raises:**
 
 - <b>`ValueError`</b>:  If the job_url path is empty. 


---

<a href="../src/github_runner_manager/reactive/consumer.py#L72"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `JobError`
Raised when a job error occurs. 





---

<a href="../src/github_runner_manager/reactive/consumer.py#L76"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `QueueError`
Raised when an error when communicating with the queue occurs. 






<!-- markdownlint-disable -->

<a href="../src/reactive/job.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `job`
Module responsible for job retrieval and handling. 



---

<a href="../src/reactive/job.py#L16"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `JobDetails`
A class to translate the payload. 



**Attributes:**
 
 - <b>`labels`</b>:  The labels of the job. 
 - <b>`run_url`</b>:  The URL of the job. 





---

<a href="../src/reactive/job.py#L28"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `MessageQueueConnectionInfo`
The connection information for the MQ. 



**Attributes:**
 
 - <b>`uri`</b>:  The URI of the MQ. 
 - <b>`queue_name`</b>:  The name of the queue. 





---

<a href="../src/reactive/job.py#L40"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `JobSourceError`
Raised when a job source error occurs. 





---

<a href="../src/reactive/job.py#L44"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `JobSource`
A protocol for a job source. 




---

<a href="../src/reactive/job.py#L47"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `ack`

```python
ack() → None
```

Acknowledge the message. 

---

<a href="../src/reactive/job.py#L53"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_job`

```python
get_job() → JobDetails
```

Get the job details from the source. 

---

<a href="../src/reactive/job.py#L50"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `reject`

```python
reject() → None
```

Reject the message. 


---

<a href="../src/reactive/job.py#L122"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `JobError`
Raised when a job error occurs. 





---

<a href="../src/reactive/job.py#L126"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `Job`
A class to represent a job to be picked up by a runner. 

<a href="../src/reactive/job.py#L129"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(job_source: JobSource)
```

Initialize the message. 



**Args:**
 
 - <b>`job_source`</b>:  The source of the job. 




---

<a href="../src/reactive/job.py#L173"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `from_message_queue`

```python
from_message_queue(mq_connection_info: MessageQueueConnectionInfo) → Job
```

Get a job from a message queue. 

This method will block until a job is available. 



**Args:**
 
 - <b>`mq_connection_info`</b>:  The connection information for the MQ. 



**Returns:**
 The retrieved Job. 

---

<a href="../src/reactive/job.py#L137"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_details`

```python
get_details() → JobDetails
```

Get the job details. 



**Raises:**
 
 - <b>`JobError`</b>:  If the job details could not be retrieved. 



**Returns:**
 The job details. 

---

<a href="../src/reactive/job.py#L162"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `picked_up`

```python
picked_up() → None
```

Indicate that the job has been picked up by a runner. 



**Raises:**
 
 - <b>`JobError`</b>:  If the job could not be acknowledged. 

---

<a href="../src/reactive/job.py#L151"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `reject`

```python
reject() → None
```

Mark the job as rejected. 



**Raises:**
 
 - <b>`JobError`</b>:  If the job could not be rejected. 



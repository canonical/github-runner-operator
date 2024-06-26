<!-- markdownlint-disable -->

<a href="../src/reactive/job.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `job`
Module responsible for job retrieval and handling. 



---

<a href="../src/reactive/job.py#L11"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `MessageQueueConnectionInfo`
The connection information for the MQ. 





---

<a href="../src/reactive/job.py#L18"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `JobSourceError`
Raised when a job source error occurs. 





---

<a href="../src/reactive/job.py#L22"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `JobSource`
A protocol for a job source. 




---

<a href="../src/reactive/job.py#L25"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `ack`

```python
ack() → None
```

Acknowledge the message. 



**Raises:**
 
 - <b>`JobSourceError`</b>:  If the job could not be acknowledged. 

---

<a href="../src/reactive/job.py#L32"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `reject`

```python
reject() → None
```

Reject the message. 



**Raises:**
 
 - <b>`JobSourceError`</b>:  If the job could not be rejected. 


---

<a href="../src/reactive/job.py#L40"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `JobError`
Raised when a job error occurs. 





---

<a href="../src/reactive/job.py#L44"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `Job`
A class to represent a job to be picked up by a runner. 

<a href="../src/reactive/job.py#L47"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(job_source: JobSource)
```

Initialize the message. 



**Args:**
 
 - <b>`job_source`</b>:  The source of the job. 


---

#### <kbd>property</kbd> labels

The labels of the job. 



**Returns:**
  The labels of the job. 

---

#### <kbd>property</kbd> run_url

The GitHub run URL of the job. 



**Returns:**
  The GitHub run URL of the job. 



---

<a href="../src/reactive/job.py#L84"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/reactive/job.py#L77"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `picked_up`

```python
picked_up() → None
```

Indicate that the job has been picked up by a runner. 



**Raises:**
 
 - <b>`JobError`</b>:  If the job could not be acknowledged. 

---

<a href="../src/reactive/job.py#L70"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `reject`

```python
reject() → None
```

Mark the job as rejected. 



**Raises:**
 
 - <b>`JobError`</b>:  If the job could not be rejected. 



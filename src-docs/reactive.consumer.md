<!-- markdownlint-disable -->

<a href="../src/reactive/consumer.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `reactive.consumer`
Module responsible for consuming jobs from the message queue. 


---

<a href="../src/reactive/consumer.py#L32"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `consume`

```python
consume(mongodb_uri: str, queue_name: str) → None
```

Consume a job from the message queue. 

Log the job details and acknowledge the message. If the job details are invalid, reject the message and raise an error. 



**Args:**
 
 - <b>`mongodb_uri`</b>:  The URI of the MongoDB database. 
 - <b>`queue_name`</b>:  The name of the queue. 



**Raises:**
 
 - <b>`JobError`</b>:  If the job details are invalid. 


---

<a href="../src/reactive/consumer.py#L28"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `JobError`
Raised when a job error occurs. 






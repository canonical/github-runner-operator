<!-- markdownlint-disable -->

<a href="../src/reactive/mq.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `mq`
Module responsible for MQ communication. 


---

<a href="../src/reactive/mq.py#L65"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `consume`

```python
consume(mq_uri: str, queue_name: str) → Message
```

Consume a messages from the MQ. 



**Args:**
 
 - <b>`mq_uri`</b>:  The URI of the MQ. 
 - <b>`queue_name`</b>:  The name of the queue. 



**Returns:**
 The consumed message. 


---

<a href="../src/reactive/mq.py#L10"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `InactiveMQError`
Raised when the connection to the MQ is inactive. 





---

<a href="../src/reactive/mq.py#L15"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `Message`
A message from the MQ. The close method should be called after the message is processed. 

Consider using `contextlib.closing` to ensure the resources are closed. 

<a href="../src/reactive/mq.py#L21"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(connection: Connection, queue_name: str)
```

Initialize the message. 



**Args:**
 
 - <b>`connection`</b>:  The connection to the MQ. 
 - <b>`queue_name`</b>:  The name of the queue. 




---

<a href="../src/reactive/mq.py#L48"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `ack`

```python
ack() → None
```

Acknowledge the message. 



**Raises:**
 
 - <b>`InactiveMQError`</b>:  If the connection to the MQ is inactive  (e.g. has already been closed or processed). 

---

<a href="../src/reactive/mq.py#L56"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `close`

```python
close() → None
```

Close the connection and the queue resources. 



**Raises:**
 
 - <b>`InactiveMQError`</b>:  If the connection to the MQ is inactive  (e.g. has already been closed or processed). 

---

<a href="../src/reactive/mq.py#L29"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_job`

```python
get_job() → Job
```

Get the job from the message. 



**Returns:**
  The consumed job. 



**Raises:**
 
 - <b>`InactiveMQError`</b>:  If the connection to the MQ is inactive  (e.g. has already been closed or processed). 

---

<a href="../src/reactive/mq.py#L40"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `reject`

```python
reject() → None
```

Do not acknowledge and requeue the message. 



**Raises:**
 
 - <b>`InactiveMQError`</b>:  If the connection to the MQ is inactive  (e.g. has already been closed or processed). 



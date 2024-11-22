<!-- markdownlint-disable -->

<a href="../../github-runner-manager/src/github_runner_manager/metrics/storage.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `metrics.storage`
Classes and functions defining the metrics storage. 

It contains a protocol and reference implementation. 



---

<a href="../../github-runner-manager/src/github_runner_manager/metrics/storage.py#L29"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `MetricsStorage`
Storage for the metrics. 



**Attributes:**
 
 - <b>`path`</b>:  The path to the directory holding the metrics inside the charm. 
 - <b>`runner_name`</b>:  The name of the associated runner. 

<a href="../../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(path: Path, runner_name: str) → None
```









---

<a href="../../github-runner-manager/src/github_runner_manager/metrics/storage.py#L42"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `StorageManagerProtocol`
A protocol defining the methods for managing the metrics storage. 



**Attributes:**
 
 - <b>`create`</b>:  Method to create a new storage. Returns the created storage.  Raises an exception CreateMetricsStorageError if the storage already exists. 
 - <b>`list_all`</b>:  Method to list all storages. 
 - <b>`get`</b>:  Method to get a storage by name. 
 - <b>`delete`</b>:  Method to delete a storage by name. 
 - <b>`move_to_quarantine`</b>:  Method to archive and delete a storage by name. 





---

<a href="../../github-runner-manager/src/github_runner_manager/metrics/storage.py#L61"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `StorageManager`
Manager for the metrics storage. 

<a href="../../github-runner-manager/src/github_runner_manager/metrics/storage.py#L64"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(system_user_config: SystemUserConfig)
```

Initialize the storage manager. 



**Args:**
 
 - <b>`system_user_config`</b>:  The configuration of the user owning the storage. 




---

<a href="../../github-runner-manager/src/github_runner_manager/metrics/storage.py#L79"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `create`

```python
create(runner_name: str) → MetricsStorage
```

Create metrics storage for the runner. 

The method is not idempotent and will raise an exception if the storage already exists. 



**Args:**
 
 - <b>`runner_name`</b>:  The name of the runner. 



**Returns:**
 The metrics storage object. 



**Raises:**
 
 - <b>`CreateMetricsStorageError`</b>:  If the creation of the shared filesystem fails. 

---

<a href="../../github-runner-manager/src/github_runner_manager/metrics/storage.py#L176"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `delete`

```python
delete(runner_name: str) → None
```

Delete the metrics storage for the runner. 



**Args:**
 
 - <b>`runner_name`</b>:  The name of the runner. 



**Raises:**
 
 - <b>`DeleteMetricsStorageError`</b>:  If the storage could not be deleted. 

---

<a href="../../github-runner-manager/src/github_runner_manager/metrics/storage.py#L156"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get`

```python
get(runner_name: str) → MetricsStorage
```

Get the metrics storage for the runner. 



**Args:**
 
 - <b>`runner_name`</b>:  The name of the runner. 



**Returns:**
 The metrics storage object. 



**Raises:**
 
 - <b>`GetMetricsStorageError`</b>:  If the storage does not exist. 

---

<a href="../../github-runner-manager/src/github_runner_manager/metrics/storage.py#L138"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `list_all`

```python
list_all() → Iterator[MetricsStorage]
```

List all the metric storages. 



**Yields:**
  A metrics storage object. 

---

<a href="../../github-runner-manager/src/github_runner_manager/metrics/storage.py#L194"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `move_to_quarantine`

```python
move_to_quarantine(runner_name: str) → None
```

Archive the metrics storage for the runner and delete it. 



**Args:**
 
 - <b>`runner_name`</b>:  The name of the runner. 



**Raises:**
 
 - <b>`QuarantineMetricsStorageError`</b>:  If the metrics storage could not be quarantined. 



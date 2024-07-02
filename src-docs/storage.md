<!-- markdownlint-disable -->

<a href="../src/metrics/storage.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `storage`
Classes and functions defining the metrics storage. 

It contains a protocol and reference implementation. 

**Global Variables**
---------------
- **FILESYSTEM_OWNER**

---

<a href="../src/metrics/storage.py#L71"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `create`

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

<a href="../src/metrics/storage.py#L104"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `list_all`

```python
list_all() → Iterator[MetricsStorage]
```

List all the metric storages. 



**Yields:**
  A metrics storage object. 


---

<a href="../src/metrics/storage.py#L123"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `get`

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

<a href="../src/metrics/storage.py#L142"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `delete`

```python
delete(runner_name: str) → None
```

Delete the metrics storage for the runner. 



**Args:**
 
 - <b>`runner_name`</b>:  The name of the runner. 



**Raises:**
 
 - <b>`DeleteMetricsStorageError`</b>:  If the storage could not be deleted. 


---

<a href="../src/metrics/storage.py#L161"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `move_to_quarantine`

```python
move_to_quarantine(storage_manager: StorageManager, runner_name: str) → None
```

Archive the metrics storage for the runner and delete it. 



**Args:**
 
 - <b>`storage_manager`</b>:  The storage manager. 
 - <b>`runner_name`</b>:  The name of the runner. 



**Raises:**
 
 - <b>`QuarantineMetricsStorageError`</b>:  If the metrics storage could not be quarantined. 


---

<a href="../src/metrics/storage.py#L29"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `MetricsStorage`
Storage for the metrics. 



**Attributes:**
 
 - <b>`path`</b>:  The path to the directory holding the metrics inside the charm. 
 - <b>`runner_name`</b>:  The name of the associated runner. 

<a href="../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(path: Path, runner_name: str) → None
```









---

<a href="../src/metrics/storage.py#L42"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `StorageManager`
A protocol defining the methods for managing the metrics storage. 



**Attributes:**
 
 - <b>`create`</b>:  Method to create a new storage. Returns the created storage.  Raises an exception CreateMetricsStorageError if the storage already exists. 
 - <b>`list_all`</b>:  Method to list all storages. 
 - <b>`get`</b>:  Method to get a storage by name. 
 - <b>`delete`</b>:  Method to delete a storage by name. 






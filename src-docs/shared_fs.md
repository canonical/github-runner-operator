<!-- markdownlint-disable -->

<a href="../src/shared_fs.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `shared_fs`
Classes and functions to operate on the shared filesystem between the charm and the runners. 

**Global Variables**
---------------
- **DIR_NO_MOUNTPOINT_EXIT_CODE**
- **FILESYSTEM_OWNER**
- **FILESYSTEM_SIZE**

---

<a href="../src/shared_fs.py#L33"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `create`

```python
create(runner_name: str) → MetricsStorage
```

Create a shared filesystem for the runner. 

The method is not idempotent and will raise an exception if the shared filesystem already exists. 



**Args:**
 
 - <b>`runner_name`</b>:  The name of the runner. 



**Returns:**
 The shared filesystem object. 



**Raises:**
 
 - <b>`CreateMetricsStorageError`</b>:  If the creation of the shared filesystem fails. 


---

<a href="../src/shared_fs.py#L71"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `list_all`

```python
list_all() → Iterator[MetricsStorage]
```

List all the metric storages. 



**Yields:**
  A metrics storage object. 


---

<a href="../src/shared_fs.py#L87"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `get`

```python
get(runner_name: str) → MetricsStorage
```

Get the shared filesystem for the runner. 

Mounts the filesystem if it is not currently mounted. 



**Args:**
 
 - <b>`runner_name`</b>:  The name of the runner. 



**Returns:**
 The shared filesystem object. 



**Raises:**
 
 - <b>`GetMetricsStorageError`</b>:  If the shared filesystem could not be retrieved/mounted. 


---

<a href="../src/shared_fs.py#L127"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `delete`

```python
delete(runner_name: str) → None
```

Delete the shared filesystem for the runner. 



**Args:**
 
 - <b>`runner_name`</b>:  The name of the runner. 



**Raises:**
 
 - <b>`DeleteMetricsStorageError`</b>:  If the shared filesystem could not be deleted. 



<!-- markdownlint-disable -->

<a href="../src/shared_fs.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `shared_fs.py`
Classes and functions to operate on the shared filesystem between the charm and the runners. 

**Global Variables**
---------------
- **FILESYSTEM_OWNER**
- **FILESYSTEM_SIZE**

---

<a href="../src/shared_fs.py#L54"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `create`

```python
create(runner_name: str) → SharedFilesystem
```

Create a shared filesystem for the runner. 

The method is not idempotent and will raise an exception if the shared filesystem already exists. 



**Args:**
 
 - <b>`runner_name`</b>:  The name of the runner. 



**Returns:**
 The shared filesystem object. 



**Raises:**
 
 - <b>`CreateSharedFilesystemError`</b>:  If the creation of the shared filesystem fails. 


---

<a href="../src/shared_fs.py#L107"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `list_all`

```python
list_all() → Iterator[SharedFilesystem]
```

List the shared filesystems. 



**Returns:**
  An iterator over shared filesystems. 


---

<a href="../src/shared_fs.py#L121"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `get`

```python
get(runner_name: str) → SharedFilesystem
```

Get the shared filesystem for the runner. 



**Args:**
 
 - <b>`runner_name`</b>:  The name of the runner. 



**Returns:**
 The shared filesystem object. 



**Raises:**
 
 - <b>`SharedFilesystemNotFoundError`</b>:  If the shared filesystem is not found. 


---

<a href="../src/shared_fs.py#L140"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `delete`

```python
delete(runner_name: str) → None
```

Delete the shared filesystem for the runner. 



**Args:**
 
 - <b>`runner_name`</b>:  The name of the runner. 



**Raises:**
 
 - <b>`DeleteSharedFilesystemError`</b>:  If the shared filesystem could not be deleted. 


---

<a href="../src/shared_fs.py#L177"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `move_to_quarantine`

```python
move_to_quarantine(runner_name: str) → None
```

Archive the shared filesystem for the runner and delete it. 



**Args:**
 
 - <b>`runner_name`</b>:  The name of the runner. 



**Raises:**
 
 - <b>`QuarantineSharedFilesystemError`</b>:  If the shared filesystem could not be quarantined. 
 - <b>`DeleteSharedFilesystemError`</b>:  If the shared filesystem could not be deleted. 


---

## <kbd>class</kbd> `SharedFilesystem`
Shared filesystem between the charm and the runners. 



**Attributes:**
 
 - <b>`path`</b>:  The path of the shared filesystem inside the charm. 
 - <b>`runner_name`</b>:  The name of the associated runner. 

**Returns:**
 The shared filesystem. 






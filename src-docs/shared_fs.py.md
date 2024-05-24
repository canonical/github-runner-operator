<!-- markdownlint-disable -->

<a href="../src/shared_fs.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `shared_fs.py`
Classes and functions to operate on the shared filesystem between the charm and the runners. 

**Global Variables**
---------------
- **DIR_NO_MOUNTPOINT_EXIT_CODE**
- **FILESYSTEM_OWNER**
- **FILESYSTEM_SIZE**

---

<a href="../src/shared_fs.py#L112"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/shared_fs.py#L162"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `list_all`

```python
list_all() → Generator[SharedFilesystem, NoneType, NoneType]
```

List the shared filesystems. 



**Yields:**
  A shared filesystem instance. 


---

<a href="../src/shared_fs.py#L181"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `get`

```python
get(runner_name: str) → SharedFilesystem
```

Get the shared filesystem for the runner. 

Mounts the filesystem if it is not currently mounted. 



**Args:**
 
 - <b>`runner_name`</b>:  The name of the runner. 



**Returns:**
 The shared filesystem object. 



**Raises:**
 
 - <b>`GetSharedFilesystemError`</b>:  If the shared filesystem could not be retrieved/mounted. 


---

<a href="../src/shared_fs.py#L267"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/shared_fs.py#L297"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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





---

## <kbd>class</kbd> `UnmountSharedFilesystemError`
Represents an error unmounting a shared filesystem. 






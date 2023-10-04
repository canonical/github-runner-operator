<!-- markdownlint-disable -->

<a href="../src/shared_fs.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `shared_fs.py`
Classes and functions to operate on the shared filesystem between the charm and the runners. 

**Global Variables**
---------------
- **FILESYSTEM_SIZE**

---

<a href="../src/shared_fs.py#L43"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `create`

```python
create(runner_name: str) → SharedFilesystem
```

Create a shared filesystem for the runner. 



**Args:**
 
 - <b>`runner_name`</b>:  The name of the runner. 



**Returns:**
 The shared filesystem object. 



**Raises:**
 
 - <b>`SubprocessError`</b>:  If the command fails. 


---

<a href="../src/shared_fs.py#L74"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `list_all`

```python
list_all() → Generator[SharedFilesystem, NoneType, NoneType]
```

List the shared filesystems. 



**Returns:**
  A generator of shared filesystems. 


---

<a href="../src/shared_fs.py#L88"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `delete`

```python
delete(runner_name: str) → None
```

Delete the shared filesystem for the runner. 



**Args:**
 
 - <b>`runner_name`</b>:  The name of the runner. 



**Raises:**
 
 - <b>`NotFoundError`</b>:  If the shared filesystem is not found. 


---

<a href="../src/shared_fs.py#L101"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `get`

```python
get(runner_name: str) → SharedFilesystem
```

Get the shared filesystem object for the runner. 

The method does not check if the filesystem exists. 



**Args:**
 
 - <b>`runner_name`</b>:  The name of the runner. 



**Returns:**
 The shared filesystem object. 



**Raises:**
 
 - <b>`NotFoundError`</b>:  If the shared filesystem is not found. 


---

## <kbd>class</kbd> `NotFoundError`
Represents an error when the shared filesystem is not found. 

<a href="../src/shared_fs.py#L34"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str)
```

Initialize a new instance of the NotFoundError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 





---

## <kbd>class</kbd> `SharedFilesystem`
Shared filesystem between the charm and the runners. 

Attrs:  path: The path of the shared filesystem inside the charm.  runner_name: The name of the associated runner. 

**Returns:**
  The shared filesystem. 






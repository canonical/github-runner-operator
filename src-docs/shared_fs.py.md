<!-- markdownlint-disable -->

<a href="../src/shared_fs.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `shared_fs.py`
Classes and functions to operate on the shared fileystem between the charm and the runners. 

**Global Variables**
---------------
- **FILESYSTEM_SIZE**

---

<a href="../src/shared_fs.py#L27"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `create`

```python
create(runner_name: str) → None
```

Create a shared filesystem for the runner. 



**Args:**
 
 - <b>`runner_name`</b>:  The name of the runner. 


---

<a href="../src/shared_fs.py#L47"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `list`

```python
list() → list[SharedFilesystem]
```

List the shared filesystems. 


---

<a href="../src/shared_fs.py#L51"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `delete`

```python
delete(runner_name: str) → None
```

Delete the shared filesystem for the runner. 



**Args:**
 
 - <b>`runner_name`</b>:  The name of the runner. 


---

<a href="../src/shared_fs.py#L60"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `get`

```python
get(runner_name: str) → SharedFilesystem
```

Get the shared filesystem for the runner. 



**Args:**
 
 - <b>`runner_name`</b>:  The name of the runner. 


---

## <kbd>class</kbd> `SharedFilesystem`
Shared filesystem between the charm and the runners. 

Attrs:  path: The path of the shared filesystem inside the charm.  runner_name: The name of the associated runner. 






<!-- markdownlint-disable -->

<a href="../src/lxd.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `lxd.py`
Low-level LXD client interface. 

The LxdClient class offer a low-level interface isolate the underlying implementation of LXD. 



---

## <kbd>class</kbd> `LxdClient`
LXD client. 

<a href="../src/lxd.py#L478"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__()
```

Construct the LXD client. 





---

## <kbd>class</kbd> `LxdInstance`
A LXD instance. 

Attrs:  name (str): Name of LXD instance.  files (LxdInstanceFiles): Manager for the files on the LXD instance.  status (str): Status of the LXD instance. 

<a href="../src/lxd.py#L157"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(pylxd_instance: 'Instance')
```

Construct the LXD instance representation. 



**Args:**
 
 - <b>`pylxd_instance`</b>:  Instance of pylxd.models.Instance for the LXD instance. 


---

#### <kbd>property</kbd> status

Status of the LXD instance. 



**Returns:**
  Status of the LXD instance. 



---

<a href="../src/lxd.py#L210"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `delete`

```python
delete(wait: 'bool' = False) → None
```

Delete the LXD instance. 



**Args:**
 
 - <b>`wait`</b>:  Whether to wait until the LXD instance stopped before returning. 



**Raises:**
 
 - <b>`LxdException`</b>:  Unable to delete the LXD instance. 

---

<a href="../src/lxd.py#L225"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `execute`

```python
execute(
    cmd: 'list[str]',
    cwd: 'Optional[str]' = None,
    hide_cmd: 'bool' = False
) → Tuple[int, IO, IO]
```

Execute a command within the LXD instance. 

Exceptions are not raise if command execution failed. Caller should check the exit code and stderr for failures. 



**Args:**
 
 - <b>`cmd`</b>:  Commands to be executed. 
 - <b>`cwd`</b>:  Working directory to execute the commands. 
 - <b>`hide_cmd`</b>:  Hide logging of cmd. 



**Returns:**
 Tuple containing the exit code, stdout, stderr. 

---

<a href="../src/lxd.py#L176"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `start`

```python
start(timeout: 'int' = 30, force: 'bool' = True, wait: 'bool' = False) → None
```

Start the LXD instance. 



**Args:**
 
 - <b>`timeout`</b>:  Timeout for starting the LXD instance. 
 - <b>`force`</b>:  Whether to force start the LXD instance. 
 - <b>`wait`</b>:  Whether to wait until the LXD instance started before returning. 



**Raises:**
 
 - <b>`LxdException`</b>:  Unable to start the LXD instance. 

---

<a href="../src/lxd.py#L193"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `stop`

```python
stop(timeout: 'int' = 30, force: 'bool' = True, wait: 'bool' = False) → None
```

Stop the LXD instance. 



**Args:**
 
 - <b>`timeout`</b>:  Timeout for stopping the LXD instance. 
 - <b>`force`</b>:  Whether to force stop the LXD instance. 
 - <b>`wait`</b>:  Whether to wait until the LXD instance stopped before returning. 



**Raises:**
 
 - <b>`LxdException`</b>:  Unable to stop the LXD instance. 


---

## <kbd>class</kbd> `LxdInstanceFileManager`
File manager of a LXD instance. 

Attrs:  instance (LxdInstance): LXD instance where the files are located in. 

<a href="../src/lxd.py#L37"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(instance: 'LxdInstance')
```

Construct the file manager. 



**Args:**
 
 - <b>`instance`</b>:  LXD instance where the files are located in. 




---

<a href="../src/lxd.py#L45"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `mk_dir`

```python
mk_dir(dir_name: 'str') → None
```

Create a directory in the LXD instance. 



**Args:**
 
 - <b>`dir`</b>:  Name of the directory to create. 

---

<a href="../src/lxd.py#L104"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `pull_file`

```python
pull_file(source: 'str', destination: 'str') → None
```

Pull a file from the LXD instance. 



**Args:**
 
 - <b>`source`</b>:  Path of the file to pull in the LXD instance. 
 - <b>`destination`</b>:  Path of load the file. 



**Raises:**
 
 - <b>`LxdException`</b>:  Unable to load the file from the LXD instance. 

---

<a href="../src/lxd.py#L53"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `push_file`

```python
push_file(
    source: 'str',
    destination: 'str',
    mode: 'Optional[str]' = None
) → None
```

Push a file to the LXD instance. 



**Args:**
 
 - <b>`source`</b>:  Path of the file to push to the LXD instance. 
 - <b>`destination`</b>:  Path in the LXD instance to load the file. 
 - <b>`mode`</b>:  File permission setting. 



**Raises:**
 
 - <b>`LxdException`</b>:  Unable to load the file into the LXD instance. 

---

<a href="../src/lxd.py#L130"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `read_file`

```python
read_file(filepath: 'str') → str
```

Read content of a file in the LXD instance. 



**Args:**
 
 - <b>`filepath`</b>:  Path of the file in the LXD instance. 



**Raises:**
 
 - <b>`LxdException`</b>:  Unable to load the file from the LXD instance. 



**Returns:**
 The content of the file. 

---

<a href="../src/lxd.py#L82"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `write_file`

```python
write_file(
    filepath: 'str',
    content: 'Union[str, bytes]',
    mode: 'Optional[str]' = None
) → None
```

Write a file with the given content in the LXD instance. 



**Args:**
 
 - <b>`filepath`</b>:  Path in the LXD instance to load the file. 
 - <b>`content`</b>:  Content of the file. 
 - <b>`mode`</b>:  File permission setting. 



**Raises:**
 
 - <b>`LxdException`</b>:  Unable to load the file to the LXD instance. 


---

## <kbd>class</kbd> `LxdInstanceManager`
LXD instance manager. 

<a href="../src/lxd.py#L254"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(pylxd_client: 'Client')
```

Construct the LXD instance manager. 



**Args:**
 
 - <b>`pylxd_client`</b>:  Instance of pylxd.Client. 




---

<a href="../src/lxd.py#L262"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `all`

```python
all() → list[LxdInstance]
```

Get list of LXD instances. 



**Raises:**
 
 - <b>`LxdException`</b>:  Unable to get all LXD instance. 



**Returns:**
 List of LXD instances. 

---

<a href="../src/lxd.py#L277"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `create`

```python
create(config: 'LxdInstanceConfig', wait: 'bool') → LxdInstance
```

Create a LXD instance. 



**Args:**
 
 - <b>`config`</b>:  Configuration for the LXD instance. 
 - <b>`wait`</b>:  Whether to wait until the LXD instance created before returning. 



**Raises:**
 
 - <b>`LxdException`</b>:  Unable to get all LXD instance. 



**Returns:**
 The created LXD instance. 


---

## <kbd>class</kbd> `LxdNetworkManager`
LXD network manager. 

<a href="../src/lxd.py#L351"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(pylxd_client: 'Client')
```

Construct the LXD profile manager. 



**Args:**
 
 - <b>`pylxd_client`</b>:  Instance of pylxd.Client. 




---

<a href="../src/lxd.py#L359"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get`

```python
get(name: 'str') → LxdNetwork
```

Get a LXD network information. 



**Args:**
 
 - <b>`name`</b>:  The name of the LXD network. 



**Returns:**
 Information on the LXD network. 


---

## <kbd>class</kbd> `LxdProfileManager`
LXD profile manager. 

<a href="../src/lxd.py#L301"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(pylxd_client: 'Client')
```

Construct the LXD profile manager. 



**Args:**
 
 - <b>`pylxd_client`</b>:  Instance of pylxd.Client. 




---

<a href="../src/lxd.py#L327"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `create`

```python
create(
    name: 'str',
    config: 'LxdResourceProfileConfig',
    devices: 'LxdResourceProfileDevices'
) → None
```

Create a LXD profile. 



**Args:**
 
 - <b>`name`</b>:  Name of the LXD profile to create. 
 - <b>`config`</b>:  Configuration of the LXD profile. devices Devices configuration of the LXD profile. 



**Raises:**
 
 - <b>`LxdException`</b>:  Unable to create the LXD profile. 

---

<a href="../src/lxd.py#L309"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `exists`

```python
exists(name: 'str') → bool
```

Check whether a LXD profile of a given name exists. 



**Args:**
 
 - <b>`name`</b>:  Name for LXD profile to check. 



**Raises:**
 
 - <b>`LxdException`</b>:  Unable to check the LXD profile existence. 



**Returns:**
 Whether the LXD profile of the given name exists. 


---

## <kbd>class</kbd> `LxdStoragePool`
A LXD storage pool. 

Attrs:  name (str): Name of the storage pool.  driver (str): Type of driver of the storage pool.  used_by (list[str]): LXD instance that uses the storage pool.  config (dict[str, any]): Dictionary of the configuration of the storage pool.  managed (bool): Whether LXD manages the storage pool. 

<a href="../src/lxd.py#L447"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(pylxd_storage_pool: 'StoragePool')
```

Construct the LXD storage pool. 



**Args:**
 
 - <b>`pylxd_storage_pool`</b>:  Instance of the pylxd.models.StoragePool. 




---

<a href="../src/lxd.py#L469"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `delete`

```python
delete()
```

Delete the storage pool. 

---

<a href="../src/lxd.py#L464"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `save`

```python
save()
```

Save the current configuration of storage pool. 


---

## <kbd>class</kbd> `LxdStoragePoolManager`
LXD storage pool manager. 

<a href="../src/lxd.py#L382"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(pylxd_client: 'Client')
```

Construct the LXD storage pool manager. 



**Args:**
 
 - <b>`pylxd_client`</b>:  Instance of pylxd.Client. 




---

<a href="../src/lxd.py#L390"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `all`

```python
all() → list[LxdStoragePool]
```

Get all LXD storage pool. 



**Returns:**
  List of LXD storage pools. 

---

<a href="../src/lxd.py#L424"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `create`

```python
create(config: 'LxdStoragePoolConfiguration') → LxdStoragePool
```

Create a LXD storage pool. 



**Args:**
 
 - <b>`config`</b>:  Configuration for the storage pool. 



**Returns:**
 The LXD storage pool. 

---

<a href="../src/lxd.py#L413"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `exists`

```python
exists(name: 'str') → bool
```

Check if a LXD storage pool exists. 



**Args:**
 
 - <b>`name`</b>:  Name to check for. 



**Returns:**
 Whether the storage pool exists. 

---

<a href="../src/lxd.py#L398"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get`

```python
get(name: 'str') → LxdStoragePool
```

Get a LXD storage pool. 



**Args:**
 
 - <b>`name`</b>:  Name of the storage pool. 



**Returns:**
 The LXD storage pool. 



<!-- markdownlint-disable -->

<a href="../src/lxd.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `lxd.py`
Low-level LXD client interface. 

The LxdClient class offers a low-level interface to isolate the underlying implementation of LXD. 

**Global Variables**
---------------
- **LXC_BINARY**


---

## <kbd>class</kbd> `LxdClient`
LXD client. 

<a href="../src/lxd.py#L583"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__() → None
```

Instantiate the LXD client. 





---

## <kbd>class</kbd> `LxdImageManager`
LXD image manager. 

<a href="../src/lxd.py#L556"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(pylxd_client: 'Client')
```

Instantiate the LXD image manager. 



**Args:**
 
 - <b>`pylxd_client`</b>:  Instance of pylxd.Client. 




---

<a href="../src/lxd.py#L564"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `create`

```python
create(name: 'str', path: 'Path') → None
```

Import a LXD image. 



**Args:**
 
 - <b>`name`</b>:  Alias for the image. 
 - <b>`path`</b>:  Path of the LXD image file. 



**Raises:**
 
 - <b>`LxdError`</b>:  Unable to import the file as LXD image. 


---

## <kbd>class</kbd> `LxdInstance`
An LXD instance. 



**Attributes:**
 
 - <b>`name`</b> (str):  Name of the LXD instance. 
 - <b>`files`</b> (LxdInstanceFiles):  Manager for the files on the LXD instance. 
 - <b>`status`</b> (str):  Status of the LXD instance. 

<a href="../src/lxd.py#L173"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(pylxd_instance: 'Instance')
```

Instantiate the LXD instance representation. 



**Args:**
 
 - <b>`pylxd_instance`</b>:  Instance of pylxd.models.Instance for the LXD  instance. 


---

#### <kbd>property</kbd> status

Status of the LXD instance. 



**Returns:**
  Status of the LXD instance. 



---

<a href="../src/lxd.py#L229"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `delete`

```python
delete(wait: 'bool' = False) → None
```

Delete the LXD instance. 



**Args:**
 
 - <b>`wait`</b>:  Whether to wait until the LXD instance is stopped before  returning. 



**Raises:**
 
 - <b>`LxdError`</b>:  Unable to delete the LXD instance. 

---

<a href="../src/lxd.py#L245"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `execute`

```python
execute(
    cmd: 'list[str]',
    cwd: 'Optional[str]' = None,
    hide_cmd: 'bool' = False,
    **kwargs: 'Any'
) → Tuple[int, IO, IO]
```

Execute a command within the LXD instance. 

Exceptions are not raised if command execution failed. Caller should check the exit code and stderr for errors. 

The command is executed with `subprocess.run`, additional arguments can be passed to it as keyword arguments. The following arguments to `subprocess.run` should not be set: `capture_output`, `shell`, `check`. As those arguments are used by this function. 



**Args:**
 
 - <b>`cmd`</b>:  Commands to be executed. 
 - <b>`cwd`</b>:  Working directory to execute the commands. 
 - <b>`hide_cmd`</b>:  Hide logging of cmd. 
 - <b>`kwargs`</b>:  Additional keyword arguments for the `subprocess.run` call. 





**Returns:**
 Tuple containing the exit code, stdout, stderr. 

---

<a href="../src/lxd.py#L193"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `start`

```python
start(timeout: 'int' = 30, force: 'bool' = True, wait: 'bool' = False) → None
```

Start the LXD instance. 



**Args:**
 
 - <b>`timeout`</b>:  Timeout for starting the LXD instance. 
 - <b>`force`</b>:  Whether to force start the LXD instance. 
 - <b>`wait`</b>:  Whether to wait until the LXD instance is started before  returning. 



**Raises:**
 
 - <b>`LxdError`</b>:  Unable to start the LXD instance. 

---

<a href="../src/lxd.py#L211"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `stop`

```python
stop(timeout: 'int' = 30, force: 'bool' = True, wait: 'bool' = False) → None
```

Stop the LXD instance. 



**Args:**
 
 - <b>`timeout`</b>:  Timeout for stopping the LXD instance. 
 - <b>`force`</b>:  Whether to force stop the LXD instance. 
 - <b>`wait`</b>:  Whether to wait until the LXD instance is stopped before  returning. 



**Raises:**
 
 - <b>`LxdError`</b>:  Unable to stop the LXD instance. 


---

## <kbd>class</kbd> `LxdInstanceFileManager`
File manager of an LXD instance. 



**Attributes:**
 
 - <b>`instance`</b> (LxdInstance):  LXD instance where the files are located in. 

<a href="../src/lxd.py#L41"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(instance: 'LxdInstance')
```

Instantiate the file manager. 



**Args:**
 
 - <b>`instance`</b>:  LXD instance where the files are located in. 




---

<a href="../src/lxd.py#L49"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `mk_dir`

```python
mk_dir(dir_name: 'str') → None
```

Create a directory in the LXD instance. 



**Args:**
 
 - <b>`dir_name`</b>:  Name of the directory to create. 

---

<a href="../src/lxd.py#L114"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `pull_file`

```python
pull_file(source: 'str', destination: 'str', is_dir: 'bool' = False) → None
```

Pull a file from the LXD instance to the local machine. 



**Args:**
 
 - <b>`source`</b>:  Path of the file to pull in the LXD instance. 
 - <b>`destination`</b>:  Path in local machine. 
 - <b>`is_dir`</b>:  Whether the source is a directory. 



**Raises:**
 
 - <b>`LxdError`</b>:  Unable to load the file from the LXD instance. 

---

<a href="../src/lxd.py#L57"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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
 - <b>`mode`</b>:  File permissions. 



**Raises:**
 
 - <b>`LxdError`</b>:  Unable to load the file into the LXD instance. 

---

<a href="../src/lxd.py#L142"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `read_file`

```python
read_file(filepath: 'str') → str
```

Read the content of a file in the LXD instance. 



**Args:**
 
 - <b>`filepath`</b>:  Path of the file in the LXD instance. 



**Raises:**
 
 - <b>`LxdError`</b>:  Unable to load the file from the LXD instance. 



**Returns:**
 The content of the file. 

---

<a href="../src/lxd.py#L88"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `write_file`

```python
write_file(
    filepath: 'str',
    content: 'Union[str, bytes]',
    mode: 'Optional[str]' = None
) → None
```

Write a file with the given content into the LXD instance. 



**Args:**
 
 - <b>`filepath`</b>:  Path in the LXD instance to load the file. 
 - <b>`content`</b>:  Content of the file. 
 - <b>`mode`</b>:  File permission setting. 



**Raises:**
 
 - <b>`LxdError`</b>:  Unable to load the file to the LXD instance. 


---

## <kbd>class</kbd> `LxdInstanceManager`
LXD instance manager. 

<a href="../src/lxd.py#L280"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(pylxd_client: 'Client')
```

Instantiate the LXD instance manager. 



**Args:**
 
 - <b>`pylxd_client`</b>:  Instance of pylxd.Client. 




---

<a href="../src/lxd.py#L288"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `all`

```python
all() → list[LxdInstance]
```

Get list of LXD instances. 



**Raises:**
 
 - <b>`LxdError`</b>:  Unable to get all LXD instances. 



**Returns:**
 List of LXD instances. 

---

<a href="../src/lxd.py#L303"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `create`

```python
create(config: 'LxdInstanceConfig', wait: 'bool') → LxdInstance
```

Create an LXD instance. 



**Args:**
 
 - <b>`config`</b>:  Configuration for the LXD instance. 
 - <b>`wait`</b>:  Whether to wait until the LXD instance is created before  returning. 



**Raises:**
 
 - <b>`LxdError`</b>:  Unable to get all LXD instances. 



**Returns:**
 The created LXD instance. 


---

## <kbd>class</kbd> `LxdNetworkManager`
LXD network manager. 

<a href="../src/lxd.py#L426"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(pylxd_client: 'Client')
```

Instantiate the LXD profile manager. 



**Args:**
 
 - <b>`pylxd_client`</b>:  Instance of pylxd.Client. 




---

<a href="../src/lxd.py#L434"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get`

```python
get(name: 'str') → LxdNetwork
```

Get the LXD network information. 



**Args:**
 
 - <b>`name`</b>:  The name of the LXD network. 



**Returns:**
 Information on the LXD network. 


---

## <kbd>class</kbd> `LxdProfile`
LXD profile. 

<a href="../src/lxd.py#L395"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(pylxd_profile: 'Profile')
```

Instantiate the LXD profile. 



**Args:**
 
 - <b>`pylxd_profile`</b>:  Instance of the pylxd.models.Profile. 




---

<a href="../src/lxd.py#L417"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `delete`

```python
delete() → None
```

Delete the profile. 

---

<a href="../src/lxd.py#L412"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `save`

```python
save() → None
```

Save the current configuration of profile. 


---

## <kbd>class</kbd> `LxdProfileManager`
LXD profile manager. 

<a href="../src/lxd.py#L328"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(pylxd_client: 'Client')
```

Instantiate the LXD profile manager. 



**Args:**
 
 - <b>`pylxd_client`</b>:  Instance of pylxd.Client. 




---

<a href="../src/lxd.py#L354"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `create`

```python
create(
    name: 'str',
    config: 'LxdResourceProfileConfig',
    devices: 'LxdResourceProfileDevices'
) → None
```

Create an LXD profile. 



**Args:**
 
 - <b>`name`</b>:  Name of the LXD profile to create. 
 - <b>`config`</b>:  Configuration of the LXD profile. 
 - <b>`devices`</b>:  Devices configuration of the LXD profile. 



**Raises:**
 
 - <b>`LxdError`</b>:  Unable to create the LXD profile. 

---

<a href="../src/lxd.py#L336"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `exists`

```python
exists(name: 'str') → bool
```

Check whether an LXD profile of a given name exists. 



**Args:**
 
 - <b>`name`</b>:  Name for LXD profile to check. 



**Raises:**
 
 - <b>`LxdError`</b>:  Unable to check the LXD profile existence. 



**Returns:**
 Whether the LXD profile of the given name exists. 

---

<a href="../src/lxd.py#L373"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get`

```python
get(name: 'str') → LxdProfile
```

Get an LXD profile. 



**Args:**
 
 - <b>`name`</b>:  Name of the LXD profile. 



**Raises:**
 
 - <b>`LxdError`</b>:  Unable to get the LXD profile with the name. 



**Returns:**
 LXDProfile with given name. 


---

## <kbd>class</kbd> `LxdStoragePool`
An LXD storage pool. 



**Attributes:**
 
 - <b>`name`</b> (str):  Name of the storage pool. 
 - <b>`driver`</b> (str):  Type of driver of the storage pool. 
 - <b>`used_by`</b> (list[str]):  LXD instances using the storage pool. 
 - <b>`config`</b> (dict[str, any]):  Dictionary of the configuration of the  storage pool. 
 - <b>`managed`</b> (bool):  Whether LXD manages the storage pool. 

<a href="../src/lxd.py#L526"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(pylxd_storage_pool: 'StoragePool')
```

Instantiate the LXD storage pool. 



**Args:**
 
 - <b>`pylxd_storage_pool`</b>:  Instance of the pylxd.models.StoragePool. 




---

<a href="../src/lxd.py#L548"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `delete`

```python
delete() → None
```

Delete the storage pool. 

---

<a href="../src/lxd.py#L543"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `save`

```python
save() → None
```

Save the current configuration of storage pool. 


---

## <kbd>class</kbd> `LxdStoragePoolManager`
LXD storage pool manager. 

<a href="../src/lxd.py#L457"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(pylxd_client: 'Client')
```

Instantiate the LXD storage pool manager. 



**Args:**
 
 - <b>`pylxd_client`</b>:  Instance of pylxd.Client. 




---

<a href="../src/lxd.py#L465"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `all`

```python
all() → list[LxdStoragePool]
```

Get all LXD storage pool. 



**Returns:**
  List of LXD storage pools. 

---

<a href="../src/lxd.py#L502"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `create`

```python
create(config: 'LxdStoragePoolConfiguration') → LxdStoragePool
```

Create an LXD storage pool. 



**Args:**
 
 - <b>`config`</b>:  Configuration for the storage pool. 



**Returns:**
 The LXD storage pool. 

---

<a href="../src/lxd.py#L491"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `exists`

```python
exists(name: 'str') → bool
```

Check if an LXD storage pool exists. 



**Args:**
 
 - <b>`name`</b>:  Name to check for. 



**Returns:**
 Whether the storage pool exists. 

---

<a href="../src/lxd.py#L473"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get`

```python
get(name: 'str') → LxdStoragePool
```

Get an LXD storage pool. 



**Args:**
 
 - <b>`name`</b>:  Name of the storage pool. 



**Raises:**
 
 - <b>`LxdError`</b>:  If the storage pool with given name was not found. 



**Returns:**
 The LXD storage pool. 



<!-- markdownlint-disable -->

<a href="../src/errors.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `errors.py`
Errors used by the charm. 



---

## <kbd>class</kbd> `CorruptMetricDataError`
Represents an error with the data being corrupt. 

<a href="../src/errors.py#L124"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: 'str')
```

Initialize a new instance of the RunnerMetricsError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 





---

## <kbd>class</kbd> `CreateSharedFilesystemError`
Represents an error when the shared filesystem could not be created. 

<a href="../src/errors.py#L104"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: 'str')
```

Initialize a new instance of the SharedFilesystemError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 





---

## <kbd>class</kbd> `LogrotateSetupError`
Error raised when logrotate cannot be setup. 





---

## <kbd>class</kbd> `LxdError`
Error for executing LXD actions. 





---

## <kbd>class</kbd> `MetricFileSizeTooLargeError`
Represents an error with the file size being too large. 

<a href="../src/errors.py#L124"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: 'str')
```

Initialize a new instance of the RunnerMetricsError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 





---

## <kbd>class</kbd> `MissingConfigurationError`
Error for missing juju configuration. 

Attrs:  configs: The missing configurations. 

<a href="../src/errors.py#L49"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(configs: 'list[str]')
```

Construct the MissingConfigurationError. 



**Args:**
 
 - <b>`configs`</b>:  The missing configurations. 





---

## <kbd>class</kbd> `MissingRunnerBinaryError`
Error for missing runner binary. 





---

## <kbd>class</kbd> `RunnerBinaryError`
Error of getting runner binary. 





---

## <kbd>class</kbd> `RunnerCreateError`
Error for runner creation failure. 





---

## <kbd>class</kbd> `RunnerError`
Generic runner error as base exception. 





---

## <kbd>class</kbd> `RunnerExecutionError`
Error for executing commands on runner. 





---

## <kbd>class</kbd> `RunnerFileLoadError`
Error for loading file on runner. 





---

## <kbd>class</kbd> `RunnerMetricsError`
Base class for all runner metrics errors. 

<a href="../src/errors.py#L124"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: 'str')
```

Initialize a new instance of the RunnerMetricsError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 





---

## <kbd>class</kbd> `RunnerRemoveError`
Error for runner removal failure. 





---

## <kbd>class</kbd> `RunnerStartError`
Error for runner start failure. 





---

## <kbd>class</kbd> `SharedFilesystemError`
Base class for all shared filesystem errors. 

<a href="../src/errors.py#L104"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: 'str')
```

Initialize a new instance of the SharedFilesystemError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 





---

## <kbd>class</kbd> `SharedFilesystemNotFoundError`
Represents an error when the shared filesystem is not found. 

<a href="../src/errors.py#L104"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: 'str')
```

Initialize a new instance of the SharedFilesystemError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 





---

## <kbd>class</kbd> `SubprocessError`
Error for Subprocess calls. 

Attrs:  cmd: Command in list form.  return_code: Return code of the subprocess.  stdout: Content of stdout of the subprocess.  stderr: Content of stderr of the subprocess. 

<a href="../src/errors.py#L74"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(
    cmd: 'list[str]',
    return_code: 'int',
    stdout: 'Union[bytes, str]',
    stderr: 'Union[bytes, str]'
)
```

Construct the subprocess error. 



**Args:**
 
 - <b>`cmd`</b>:  Command in list form. 
 - <b>`return_code`</b>:  Return code of the subprocess. 
 - <b>`stdout`</b>:  Content of stdout of the subprocess. 
 - <b>`stderr`</b>:  Content of stderr of the subprocess. 






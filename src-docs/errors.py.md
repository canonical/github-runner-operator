<!-- markdownlint-disable -->

<a href="../src/errors.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `errors.py`
Errors used by the charm. 



---

## <kbd>class</kbd> `ConfigurationError`
Error for juju configuration. 





---

## <kbd>class</kbd> `IssueMetricEventError`
Represents an error when issuing a metric event. 





---

## <kbd>class</kbd> `LogrotateSetupError`
Represents an error raised when logrotate cannot be setup. 





---

## <kbd>class</kbd> `LxdError`
Error for executing LXD actions. 





---

## <kbd>class</kbd> `MissingMongoDBError`
Error for missing integration data. 





---

## <kbd>class</kbd> `MissingRunnerBinaryError`
Error for missing runner binary. 





---

## <kbd>class</kbd> `MissingServerConfigError`
Error for unable to create runner due to missing server configurations. 





---

## <kbd>class</kbd> `RunnerAproxyError`
Error for setting up aproxy. 





---

## <kbd>class</kbd> `RunnerBinaryError`
Error of getting runner binary. 





---

## <kbd>class</kbd> `RunnerCreateError`
Error for runner creation failure. 





---

## <kbd>class</kbd> `RunnerFileLoadError`
Error for loading file on runner. 





---

## <kbd>class</kbd> `RunnerLogsError`
Base class for all runner logs errors. 





---

## <kbd>class</kbd> `RunnerRemoveError`
Error for runner removal failure. 





---

## <kbd>class</kbd> `SharedFilesystemError`
Base class for all shared filesystem errors. 





---

## <kbd>class</kbd> `SharedFilesystemMountError`
Represents an error related to the mounting of the shared filesystem. 





---

## <kbd>class</kbd> `SubprocessError`
Error for Subprocess calls. 



**Attributes:**
 
 - <b>`cmd`</b>:  Command in list form. 
 - <b>`return_code`</b>:  Return code of the subprocess. 
 - <b>`stdout`</b>:  Content of stdout of the subprocess. 
 - <b>`stderr`</b>:  Content of stderr of the subprocess. 

<a href="../src/errors.py#L72"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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






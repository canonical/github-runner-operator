<!-- markdownlint-disable -->

<a href="../src/errors.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `errors.py`
Errors used by the charm. 



---

## <kbd>class</kbd> `ConfigurationError`
Error for juju configuration. 





---

## <kbd>class</kbd> `CorruptMetricDataError`
Represents an error with the data being corrupt. 





---

## <kbd>class</kbd> `CreateSharedFilesystemError`
Represents an error when the shared filesystem could not be created. 





---

## <kbd>class</kbd> `DeleteSharedFilesystemError`
Represents an error when the shared filesystem could not be deleted. 





---

## <kbd>class</kbd> `GetSharedFilesystemError`
Represents an error when the shared filesystem could not be retrieved. 





---

## <kbd>class</kbd> `GithubApiError`
Represents an error when the GitHub API returns an error. 





---

## <kbd>class</kbd> `GithubClientError`
Base class for all github client errors. 





---

## <kbd>class</kbd> `GithubMetricsError`
Base class for all github metrics errors. 





---

## <kbd>class</kbd> `IssueMetricEventError`
Represents an error when issuing a metric event. 





---

## <kbd>class</kbd> `JobNotFoundError`
Represents an error when the job could not be found on GitHub. 





---

## <kbd>class</kbd> `LogrotateSetupError`
Represents an error raised when logrotate cannot be setup. 





---

## <kbd>class</kbd> `LxdError`
Error for executing LXD actions. 





---

## <kbd>class</kbd> `MissingConfigurationError`
Error for missing juju configuration. 



**Attributes:**
 
 - <b>`configs`</b>:  The missing configurations. 

<a href="../src/errors.py#L53"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

## <kbd>class</kbd> `QuarantineSharedFilesystemError`
Represents an error when the shared filesystem could not be quarantined. 





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

## <kbd>class</kbd> `RunnerError`
Generic runner error as base exception. 





---

## <kbd>class</kbd> `RunnerExecutionError`
Error for executing commands on runner. 





---

## <kbd>class</kbd> `RunnerFileLoadError`
Error for loading file on runner. 





---

## <kbd>class</kbd> `RunnerLogsError`
Base class for all runner logs errors. 





---

## <kbd>class</kbd> `RunnerMetricsError`
Base class for all runner metrics errors. 





---

## <kbd>class</kbd> `RunnerRemoveError`
Error for runner removal failure. 





---

## <kbd>class</kbd> `RunnerStartError`
Error for runner start failure. 





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

<a href="../src/errors.py#L82"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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





---

## <kbd>class</kbd> `TokenError`
Represents an error when the token is invalid. 






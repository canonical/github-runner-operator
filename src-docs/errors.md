<!-- markdownlint-disable -->

<a href="../src/errors.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `errors`
Errors used by the charm. 



---

<a href="../src/errors.py#L10"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerError`
Generic runner error as base exception. 





---

<a href="../src/errors.py#L14"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerExecutionError`
Error for executing commands on runner. 





---

<a href="../src/errors.py#L18"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerFileLoadError`
Error for loading file on runner. 





---

<a href="../src/errors.py#L22"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerCreateError`
Error for runner creation failure. 





---

<a href="../src/errors.py#L26"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerRemoveError`
Error for runner removal failure. 





---

<a href="../src/errors.py#L30"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerStartError`
Error for runner start failure. 





---

<a href="../src/errors.py#L34"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerBinaryError`
Error of getting runner binary. 





---

<a href="../src/errors.py#L38"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerAproxyError`
Error for setting up aproxy. 





---

<a href="../src/errors.py#L42"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `MissingRunnerBinaryError`
Error for missing runner binary. 





---

<a href="../src/errors.py#L46"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `ConfigurationError`
Error for juju configuration. 





---

<a href="../src/errors.py#L50"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `MissingMongoDBError`
Error for missing integration data. 





---

<a href="../src/errors.py#L54"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `LxdError`
Error for executing LXD actions. 





---

<a href="../src/errors.py#L58"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `SubprocessError`
Error for Subprocess calls. 



**Attributes:**
 
 - <b>`cmd`</b>:  Command in list form. 
 - <b>`return_code`</b>:  Return code of the subprocess. 
 - <b>`stdout`</b>:  Content of stdout of the subprocess. 
 - <b>`stderr`</b>:  Content of stderr of the subprocess. 

<a href="../src/errors.py#L68"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

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

<a href="../src/errors.py#L91"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `IssueMetricEventError`
Represents an error when issuing a metric event. 





---

<a href="../src/errors.py#L95"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `LogrotateSetupError`
Represents an error raised when logrotate cannot be setup. 





---

<a href="../src/errors.py#L99"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `MetricsStorageError`
Base class for all metrics storage errors. 





---

<a href="../src/errors.py#L103"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `SharedFilesystemError`
Base class for all shared filesystem errors. 





---

<a href="../src/errors.py#L107"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `CreateMetricsStorageError`
Represents an error when the metrics storage could not be created. 





---

<a href="../src/errors.py#L111"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `DeleteMetricsStorageError`
Represents an error when the metrics storage could not be deleted. 





---

<a href="../src/errors.py#L115"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `GetMetricsStorageError`
Represents an error when the metrics storage could not be retrieved. 





---

<a href="../src/errors.py#L119"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `QuarantineMetricsStorageError`
Represents an error when the metrics storage could not be quarantined. 





---

<a href="../src/errors.py#L123"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `SharedFilesystemMountError`
Represents an error related to the mounting of the shared filesystem. 





---

<a href="../src/errors.py#L127"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerMetricsError`
Base class for all runner metrics errors. 





---

<a href="../src/errors.py#L131"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `CorruptMetricDataError`
Represents an error with the data being corrupt. 





---

<a href="../src/errors.py#L135"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `GithubMetricsError`
Base class for all github metrics errors. 





---

<a href="../src/errors.py#L139"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `GithubClientError`
Base class for all github client errors. 





---

<a href="../src/errors.py#L143"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `GithubApiError`
Represents an error when the GitHub API returns an error. 





---

<a href="../src/errors.py#L147"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `TokenError`
Represents an error when the token is invalid or has not enough permissions. 





---

<a href="../src/errors.py#L151"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `JobNotFoundError`
Represents an error when the job could not be found on GitHub. 





---

<a href="../src/errors.py#L155"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerLogsError`
Base class for all runner logs errors. 





---

<a href="../src/errors.py#L159"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `OpenstackError`
Base class for OpenStack errors. 





---

<a href="../src/errors.py#L163"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `OpenStackInvalidConfigError`
Represents an invalid OpenStack configuration. 





---

<a href="../src/errors.py#L167"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `OpenStackUnauthorizedError`
Represents an unauthorized connection to OpenStack. 





---

<a href="../src/errors.py#L171"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `SshError`
Represents an error while interacting with SSH. 





---

<a href="../src/errors.py#L175"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `KeyfileError`
Represents missing keyfile for SSH. 






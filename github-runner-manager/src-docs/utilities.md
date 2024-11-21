<!-- markdownlint-disable -->

<a href="../src/github_runner_manager/utilities.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `utilities`
Utilities used by the charm. 


---

<a href="../src/github_runner_manager/utilities.py#L25"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `retry`

```python
retry(
    exception: Type[Exception] = <class 'Exception'>,
    tries: int = 1,
    delay: float = 0,
    max_delay: Optional[float] = None,
    backoff: float = 1,
    local_logger: Logger = <Logger utilities (WARNING)>
) → Callable[[Callable[~ParamT, ~ReturnT]], Callable[~ParamT, ~ReturnT]]
```

Parameterize the decorator for adding retry to functions. 



**Args:**
 
 - <b>`exception`</b>:  Exception type to be retried. 
 - <b>`tries`</b>:  Number of attempts at retry. 
 - <b>`delay`</b>:  Time in seconds to wait between retry. 
 - <b>`max_delay`</b>:  Max time in seconds to wait between retry. 
 - <b>`backoff`</b>:  Factor to increase the delay by each retry. 
 - <b>`local_logger`</b>:  Logger for logging. 



**Returns:**
 The function decorator for retry. 


---

<a href="../src/github_runner_manager/utilities.py#L107"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `secure_run_subprocess`

```python
secure_run_subprocess(
    cmd: Sequence[str],
    hide_cmd: bool = False,
    **kwargs: dict[str, Any]
) → CompletedProcess[bytes]
```

Run command in subprocess according to security recommendations. 

CalledProcessError will not be raised on error of the command executed. Errors should be handled by the caller by checking the exit code. 

The command is executed with `subprocess.run`, additional arguments can be passed to it as keyword arguments. The following arguments to `subprocess.run` should not be set: `capture_output`, `shell`, `check`. As those arguments are used by this function. 



**Args:**
 
 - <b>`cmd`</b>:  Command in a list. 
 - <b>`hide_cmd`</b>:  Hide logging of cmd. 
 - <b>`kwargs`</b>:  Additional keyword arguments for the `subprocess.run` call. 



**Returns:**
 Object representing the completed process. The outputs subprocess can accessed. 


---

<a href="../src/github_runner_manager/utilities.py#L148"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `set_env_var`

```python
set_env_var(env_var: str, value: str) → None
```

Set the environment variable value. 

Set the all upper case and all low case of the `env_var`. 



**Args:**
 
 - <b>`env_var`</b>:  Name of the environment variable. 
 - <b>`value`</b>:  Value to set environment variable to. 



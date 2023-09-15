<!-- markdownlint-disable -->

<a href="../src/utilities.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `utilities.py`
Utilities used by the charm. 


---

<a href="../src/utilities.py#L27"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `retry`

```python
retry(
    exception: Type[Exception] = <class 'Exception'>,
    tries: int = 1,
    delay: float = 0,
    max_delay: Optional[float] = None,
    backoff: float = 1,
    local_logger: Logger = <Logger utilities.py (WARNING)>
) → Callable[[Callable[~ParamT, ~ReturnT]], Callable[~ParamT, ~ReturnT]]
```

Parameterize the decorator for adding retry to functions. 



**Args:**
 
 - <b>`exception`</b>:  Exception type to be retried. 
 - <b>`tries`</b>:  Number of attempts at retry. 
 - <b>`delay`</b>:  Time in seconds to wait between retry. 
 - <b>`max_delay`</b>:  Max time in seconds to wait between retry. 
 - <b>`backoff`</b>:  Factor to increase the delay by each retry. 
 - <b>`logger`</b>:  Logger for logging. 



**Returns:**
 The function decorator for retry. 


---

<a href="../src/utilities.py#L98"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `secure_run_subprocess`

```python
secure_run_subprocess(
    cmd: Sequence[str],
    hide_cmd: bool = False,
    **kwargs
) → CompletedProcess[bytes]
```

Run command in subprocess according to security recommendations. 

The argument `shell` is set to `False` for security reasons. 

The argument `check` is set to `False`, therefore, CalledProcessError will not be raised. Errors are handled by the caller by checking the exit code. 



**Args:**
 
 - <b>`cmd`</b>:  Command in a list. 
 - <b>`hide_cmd`</b>:  Hide logging of cmd. 
 - <b>`kwargs`</b>:  Additional keyword arguments for the `subprocess.run` call. 



**Returns:**
 Object representing the completed process. The outputs subprocess can accessed. 


---

<a href="../src/utilities.py#L136"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `execute_command`

```python
execute_command(
    cmd: Sequence[str],
    check_exit: bool = True,
    **kwargs
) → tuple[str, int]
```

Execute a command on a subprocess. 

The command is executed with `subprocess.run`, additional arguments can be passed to it as keyword arguments. The following arguments to `subprocess.run` should not be set: `capture_output`, `shell`, `check`. As those arguments are used by this function. 



**Args:**
 
 - <b>`cmd`</b>:  Command in a list. 
 - <b>`check_exit`</b>:  Whether to check for non-zero exit code and raise exceptions. 
 - <b>`kwargs`</b>:  Additional keyword arguments for the `subprocess.run` call. 



**Returns:**
 Output on stdout, and the exit code. 


---

<a href="../src/utilities.py#L172"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `get_env_var`

```python
get_env_var(env_var: str) → Optional[str]
```

Get the environment variable value. 

Looks for all upper-case and all low-case of the `env_var`. 



**Args:**
 
 - <b>`env_var`</b>:  Name of the environment variable. 



**Returns:**
 Value of the environment variable. None if not found. 


---

<a href="../src/utilities.py#L186"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `set_env_var`

```python
set_env_var(env_var: str, value: str) → None
```

Set the environment variable value. 

Set the all upper case and all low case of the `env_var`. 



**Args:**
 
 - <b>`env_var`</b>:  Name of the environment variable. 
 - <b>`value`</b>:  Value to set environment variable to. 


---

<a href="../src/utilities.py#L199"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `bytes_with_unit_to_kib`

```python
bytes_with_unit_to_kib(num_bytes: str) → int
```

Convert a positive integer followed by a unit to number of kibibytes. 



**Args:**
 
 - <b>`num_bytes`</b>:  A positive integer followed by one of the following unit: KiB, MiB, GiB, TiB,  PiB, EiB. 

**Returns:**
 Number of kilobytes. 



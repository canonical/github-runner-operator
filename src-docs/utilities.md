<!-- markdownlint-disable -->

<a href="../src/utilities.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `utilities`
Utilities used by the charm. 


---

<a href="../src/utilities.py#L31"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `execute_command`

```python
execute_command(
    cmd: Sequence[str],
    check_exit: bool = True,
    **kwargs: Any
) → tuple[str, int]
```

Execute a command on a subprocess. 

The command is executed with `subprocess.run`, additional arguments can be passed to it as keyword arguments. The following arguments to `subprocess.run` should not be set: `capture_output`, `shell`, `check`. As those arguments are used by this function. 

The output is logged if the log level of the logger is set to debug. 



**Args:**
 
 - <b>`cmd`</b>:  Command in a list. 
 - <b>`check_exit`</b>:  Whether to check for non-zero exit code and raise exceptions. 
 - <b>`kwargs`</b>:  Additional keyword arguments for the `subprocess.run` call. 



**Returns:**
 Output on stdout, and the exit code. 



**Raises:**
 
 - <b>`SubprocessError`</b>:  If `check_exit` is set and the exit code is non-zero. 


---

<a href="../src/utilities.py#L72"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/utilities.py#L86"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `bytes_with_unit_to_kib`

```python
bytes_with_unit_to_kib(num_bytes: str) → int
```

Convert a positive integer followed by a unit to number of kibibytes. 



**Args:**
 
 - <b>`num_bytes`</b>:  A positive integer followed by one of the following unit: KiB, MiB, GiB, TiB,  PiB, EiB. 



**Raises:**
 
 - <b>`ValueError`</b>:  If invalid unit was detected. 



**Returns:**
 Number of kilobytes. 


---

<a href="../src/utilities.py#L119"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `remove_residual_venv_dirs`

```python
remove_residual_venv_dirs() → None
```

Remove the residual empty directories from last revision if it exists. 



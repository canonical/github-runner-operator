<!-- markdownlint-disable -->

<a href="../src/github_runner_manager/reactive/process_manager.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `reactive.process_manager`
Module for managing processes which spawn runners reactively. 

**Global Variables**
---------------
- **PYTHON_BIN**
- **REACTIVE_RUNNER_SCRIPT_MODULE**
- **REACTIVE_RUNNER_CMD_LINE_PREFIX**
- **PID_CMD_COLUMN_WIDTH**
- **PIDS_COMMAND_LINE**
- **UBUNTU_USER**
- **RUNNER_CONFIG_ENV_VAR**

---

<a href="../src/github_runner_manager/reactive/process_manager.py#L41"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `reconcile`

```python
reconcile(quantity: int, runner_config: RunnerConfig) → int
```

Reconcile the number of reactive runner processes. 



**Args:**
 
 - <b>`quantity`</b>:  The number of processes to spawn. 
 - <b>`runner_config`</b>:  The reactive runner configuration. 

Raises a ReactiveRunnerError if the runner fails to spawn. 



**Returns:**
 The number of reactive runner processes spawned/killed. 


---

<a href="../src/github_runner_manager/reactive/process_manager.py#L37"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `ReactiveRunnerError`
Raised when a reactive runner error occurs. 






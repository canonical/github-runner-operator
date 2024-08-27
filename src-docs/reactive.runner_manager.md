<!-- markdownlint-disable -->

<a href="../src/reactive/runner_manager.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `reactive.runner_manager`
Module for managing reactive runners. 

**Global Variables**
---------------
- **MQ_URI_ENV_VAR**
- **QUEUE_NAME_ENV_VAR**
- **REACTIVE_RUNNER_SCRIPT_FILE**
- **PYTHON_BIN**
- **REACTIVE_RUNNER_CMD_LINE_PREFIX**
- **PID_CMD_COLUMN_WIDTH**
- **PIDS_COMMAND_LINE**
- **UBUNTU_USER**

---

<a href="../src/reactive/runner_manager.py#L41"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `reconcile`

```python
reconcile(
    quantity: int,
    mq_uri: Annotated[MultiHostUrl, UrlConstraints(max_length=None, allowed_schemes=['mongodb', 'mongodb+srv'], host_required=None, default_host=None, default_port=27017, default_path=None)],
    queue_name: str
) → int
```

Spawn a runner reactively. 



**Args:**
 
 - <b>`quantity`</b>:  The number of runners to spawn. 
 - <b>`mq_uri`</b>:  The message queue URI. 
 - <b>`queue_name`</b>:  The name of the queue. 

Raises a ReactiveRunnerError if the runner fails to spawn. 



**Returns:**
 The number of reactive runner processes spawned. 


---

<a href="../src/reactive/runner_manager.py#L37"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `ReactiveRunnerError`
Raised when a reactive runner error occurs. 






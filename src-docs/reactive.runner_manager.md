<!-- markdownlint-disable -->

<a href="../src/reactive/runner_manager.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `reactive.runner_manager`
Module for managing reactive runners. 

**Global Variables**
---------------
- **MQ_URI_ENV_VAR**
- **REACTIVE_RUNNER_SCRIPT_FILE**
- **REACTIVE_RUNNER_TIMEOUT_STR**
- **PYTHON_BIN**
- **PS_COMMAND_LINE_LIST**
- **TIMEOUT_COMMAND**
- **UBUNTU_USER**

---

<a href="../src/reactive/runner_manager.py#L62"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `reconcile`

```python
reconcile(quantity: int, config: ReactiveRunnerConfig) → int
```

Spawn a runner reactively. 



**Args:**
 
 - <b>`quantity`</b>:  The number of runners to spawn. 
 - <b>`config`</b>:  The configuration for the reactive runner. 

Raises a ReactiveRunnerError if the runner fails to spawn. 



**Returns:**
 The number of runners spawned. 


---

<a href="../src/reactive/runner_manager.py#L45"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `ReactiveRunnerError`
Raised when a reactive runner error occurs. 





---

<a href="../src/reactive/runner_manager.py#L49"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `ReactiveRunnerConfig`
Configuration for spawning a reactive runner. 



**Attributes:**
 
 - <b>`mq_uri`</b>:  The message queue URI. 
 - <b>`queue_name`</b>:  The name of the queue. 

<a href="../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(mq_uri: str, queue_name: str) → None
```










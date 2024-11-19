<!-- markdownlint-disable -->

<a href="../src/github_runner_manager/manager/runner_scaler.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `manager.runner_scaler`
Module for scaling the runners amount. 



---

<a href="../src/github_runner_manager/manager/runner_scaler.py#L31"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerInfo`
Information on the runners. 



**Attributes:**
 
 - <b>`online`</b>:  The number of runner in online state. 
 - <b>`busy`</b>:  The number of the runner in busy state. 
 - <b>`offline`</b>:  The number of runner in offline state. 
 - <b>`unknown`</b>:  The number of runner in unknown state. 
 - <b>`runners`</b>:  The names of the online runners. 
 - <b>`busy_runners`</b>:  The names of the busy runners. 

<a href="../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    online: int,
    busy: int,
    offline: int,
    unknown: int,
    runners: tuple[str, ],
    busy_runners: tuple[str, ]
) → None
```









---

<a href="../src/github_runner_manager/manager/runner_scaler.py#L87"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerScaler`
Manage the reconcile of runners. 

<a href="../src/github_runner_manager/manager/runner_scaler.py#L90"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    runner_manager: RunnerManager,
    reactive_runner_config: RunnerConfig | None
)
```

Construct the object. 



**Args:**
 
 - <b>`runner_manager`</b>:  The RunnerManager to perform runner reconcile. 
 - <b>`reactive_runner_config`</b>:  Reactive runner configuration. 




---

<a href="../src/github_runner_manager/manager/runner_scaler.py#L138"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `flush`

```python
flush(flush_mode: FlushMode = <FlushMode.FLUSH_IDLE: 1>) → int
```

Flush the runners. 



**Args:**
 
 - <b>`flush_mode`</b>:  Determines the types of runner to be flushed. 



**Returns:**
 Number of runners flushed. 

---

<a href="../src/github_runner_manager/manager/runner_scaler.py#L102"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_runner_info`

```python
get_runner_info() → RunnerInfo
```

Get information on the runners. 



**Returns:**
  The information on the runners. 

---

<a href="../src/github_runner_manager/manager/runner_scaler.py#L156"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `reconcile`

```python
reconcile(quantity: int) → int
```

Reconcile the quantity of runners. 



**Args:**
 
 - <b>`quantity`</b>:  The number of intended runners. 



**Returns:**
 The Change in number of runners or reactive processes. 



**Raises:**
 
 - <b>`ReconcileError`</b>:  If an expected error occurred during the reconciliation. 



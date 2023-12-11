<!-- markdownlint-disable -->

<a href="../src/runner_logs.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `runner_logs.py`
Functions to pull and remove the logs of the crashed runners. 

**Global Variables**
---------------
- **OUTDATED_LOGS_IN_SECONDS**

---

<a href="../src/runner_logs.py#L23"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `get_crashed`

```python
get_crashed(runner: Runner) → None
```

Pull the logs of the crashed runner and put them in a directory named after the runner. 

Expects the runner to have an instance. 



**Args:**
 
 - <b>`runner`</b>:  The runner. 


---

<a href="../src/runner_logs.py#L45"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `remove_outdated_crashed`

```python
remove_outdated_crashed() → None
```

Remove the logs of the crashed runners that are too old. 



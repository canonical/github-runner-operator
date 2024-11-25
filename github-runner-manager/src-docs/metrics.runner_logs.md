<!-- markdownlint-disable -->

<a href="../../github-runner-manager/src/github_runner_manager/metrics/runner_logs.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `metrics.runner_logs`
Functions to pull and remove the logs of the crashed runners. 

**Global Variables**
---------------
- **OUTDATED_LOGS_IN_SECONDS**

---

<a href="../../github-runner-manager/src/github_runner_manager/metrics/runner_logs.py#L21"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `create_logs_dir`

```python
create_logs_dir(runner_name: str) → Path
```

Create the directory to store the logs of the crashed runners. 



**Args:**
 
 - <b>`runner_name`</b>:  The name of the runner. 



**Returns:**
 The path to the directory where the logs of the crashed runners will be stored. 


---

<a href="../../github-runner-manager/src/github_runner_manager/metrics/runner_logs.py#L36"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `remove_outdated`

```python
remove_outdated() → None
```

Remove the logs that are too old. 



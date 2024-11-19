<!-- markdownlint-disable -->

<a href="../src/github_runner_manager/reactive/runner.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `reactive.runner`
Script to spawn a reactive runner process. 

**Global Variables**
---------------
- **RUNNER_CONFIG_ENV_VAR**

---

<a href="../src/github_runner_manager/reactive/runner.py#L18"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `setup_root_logging`

```python
setup_root_logging() → None
```

Set up logging for the reactive runner process. 


---

<a href="../src/github_runner_manager/reactive/runner.py#L28"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `main`

```python
main() → None
```

Spawn a process that consumes a message from the queue to create a runner. 



**Raises:**
 
 - <b>`ValueError`</b>:  If the required environment variables are not set 



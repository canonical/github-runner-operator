<!-- markdownlint-disable -->

<a href="../src/charm.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `charm.py`
Charm for creating and managing GitHub self-hosted runner instances. 

**Global Variables**
---------------
- **DEBUG_SSH_INTEGRATION_NAME**
- **GROUP_CONFIG_NAME**
- **IMAGE_INTEGRATION_NAME**
- **LABELS_CONFIG_NAME**
- **PATH_CONFIG_NAME**
- **RECONCILE_INTERVAL_CONFIG_NAME**
- **TOKEN_CONFIG_NAME**
- **RECONCILIATION_INTERVAL_TIMEOUT_FACTOR**
- **RECONCILE_RUNNERS_EVENT**
- **REACTIVE_MQ_DB_NAME**
- **GITHUB_SELF_HOSTED_ARCH_LABELS**
- **ROOT_USER**
- **RUNNER_MANAGER_USER**
- **RUNNER_MANAGER_GROUP**
- **ACTIVE_STATUS_RECONCILIATION_FAILED_MSG**
- **FAILED_TO_RECONCILE_RUNNERS_MSG**
- **FAILED_RECONCILE_ACTION_ERR_MSG**

---

<a href="../src/charm.py#L117"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `catch_charm_errors`

```python
catch_charm_errors(
    func: Callable[[ForwardRef('GithubRunnerCharm'), ~EventT], NoneType]
) → Callable[[ForwardRef('GithubRunnerCharm'), ~EventT], NoneType]
```

Catch common errors in charm. 



**Args:**
 
 - <b>`func`</b>:  Charm function to be decorated. 



**Returns:**
 Decorated charm function with catching common errors. 


---

<a href="../src/charm.py#L152"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `catch_action_errors`

```python
catch_action_errors(
    func: Callable[[ForwardRef('GithubRunnerCharm'), ActionEvent], NoneType]
) → Callable[[ForwardRef('GithubRunnerCharm'), ActionEvent], NoneType]
```

Catch common errors in actions. 



**Args:**
 
 - <b>`func`</b>:  Action function to be decorated. 



**Returns:**
 Decorated charm function with catching common errors. 


---

## <kbd>class</kbd> `GithubRunnerCharm`
Charm for managing GitHub self-hosted runners. 

<a href="../src/charm.py#L187"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(*args: Any, **kwargs: Any) → None
```

Construct the charm. 



**Args:**
 
 - <b>`args`</b>:  List of arguments to be passed to the `CharmBase` class. 
 - <b>`kwargs`</b>:  List of keyword arguments to be passed to the `CharmBase`  class. 


---

#### <kbd>property</kbd> app

Application that this unit is part of. 

---

#### <kbd>property</kbd> charm_dir

Root directory of the charm as it is running. 

---

#### <kbd>property</kbd> config

A mapping containing the charm's config and current values. 

---

#### <kbd>property</kbd> meta

Metadata of this charm. 

---

#### <kbd>property</kbd> model

Shortcut for more simple access the model. 

---

#### <kbd>property</kbd> unit

Unit that this execution is responsible for. 




---

## <kbd>class</kbd> `ReconcileRunnersEvent`
Event representing a periodic check to ensure runners are ok. 






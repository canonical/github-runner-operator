<!-- markdownlint-disable -->

<a href="../src/charm.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `charm`
Charm for creating and managing GitHub self-hosted runner instances. 

**Global Variables**
---------------
- **DEBUG_SSH_INTEGRATION_NAME**
- **GROUP_CONFIG_NAME**
- **IMAGE_INTEGRATION_NAME**
- **LABELS_CONFIG_NAME**
- **PATH_CONFIG_NAME**
- **RECONCILE_INTERVAL_CONFIG_NAME**
- **TEST_MODE_CONFIG_NAME**
- **TOKEN_CONFIG_NAME**
- **RECONCILIATION_INTERVAL_TIMEOUT_FACTOR**
- **RECONCILE_RUNNERS_EVENT**
- **REACTIVE_MQ_DB_NAME**

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

<a href="../src/charm.py#L158"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/charm.py#L110"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `ReconcileRunnersEvent`
Event representing a periodic check to ensure runners are ok. 





---

<a href="../src/charm.py#L196"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `GithubRunnerCharm`
Charm for managing GitHub self-hosted runners. 



**Attributes:**
 
 - <b>`service_token_path`</b>:  The path to token to access local services. 
 - <b>`repo_check_web_service_path`</b>:  The path to repo-policy-compliance service directory. 
 - <b>`repo_check_web_service_script`</b>:  The path to repo-policy-compliance web service script. 
 - <b>`repo_check_systemd_service`</b>:  The path to repo-policy-compliance unit file. 
 - <b>`juju_storage_path`</b>:  The path to juju storage. 
 - <b>`ram_pool_path`</b>:  The path to memdisk storage. 
 - <b>`kernel_module_path`</b>:  The path to kernel modules. 

<a href="../src/charm.py#L219"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(*args: Any, **kwargs: Any) → None
```

Construct the charm. 



**Args:**
 
 - <b>`args`</b>:  List of arguments to be passed to the `CharmBase` class. 
 - <b>`kwargs`</b>:  List of keyword arguments to be passed to the `CharmBase`  class. 



**Raises:**
 
 - <b>`RuntimeError`</b>:  If invalid test configuration was detected. 


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





<!-- markdownlint-disable -->

<a href="../src/github_runner_manager/reactive/runner_manager.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `reactive.runner_manager`
Module for reconciling amount of runner and reactive runner processes. 


---

<a href="../src/github_runner_manager/reactive/runner_manager.py#L34"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `reconcile`

```python
reconcile(
    expected_quantity: int,
    runner_manager: RunnerManager,
    runner_config: RunnerConfig
) → ReconcileResult
```

Reconcile runners reactively. 

The reconciliation attempts to make the following equation true:  quantity_of_current_runners + amount_of_reactive_processes_consuming_jobs  == expected_quantity 

A few examples: 

1. If there are 5 runners and 5 reactive processes and the quantity is 10,  no action is taken. 2. If there are 5 runners and 5 reactive processes and the quantity is 15,  5 reactive processes are created. 3. If there are 5 runners and 5 reactive processes and quantity is 7,  3 reactive processes are killed. 4. If there are 5 runners and 5 reactive processes and quantity is 5,  all reactive processes are killed. 5. If there are 5 runners and 5 reactive processes and quantity is 4,  1 runner is killed and all reactive processes are killed. 



So if the quantity is equal to the sum of the current runners and reactive processes, no action is taken, 

If the quantity is greater than the sum of the current runners and reactive processes, additional reactive processes are created. 

If the quantity is greater than or equal to the quantity of the current runners, but less than the sum of the current runners and reactive processes, additional reactive processes will be killed. 

If the quantity is less than the sum of the current runners, additional runners are killed and all reactive processes are killed. 

In addition to this behaviour, reconciliation also checks the queue at the start and removes all idle runners if the queue is empty, to ensure that no idle runners are left behind if there are no new jobs. 



**Args:**
 
 - <b>`expected_quantity`</b>:  Number of intended amount of runners + reactive processes. 
 - <b>`runner_manager`</b>:  The runner manager to interact with current running runners. 
 - <b>`runner_config`</b>:  The reactive runner config. 



**Returns:**
 The number of reactive processes created. If negative, its absolute value is equal to the number of processes killed. 


---

<a href="../src/github_runner_manager/reactive/runner_manager.py#L21"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `ReconcileResult`
The result of the reconciliation. 



**Attributes:**
 
 - <b>`processes_diff`</b>:  The number of reactive processes created/removed. 
 - <b>`metric_stats`</b>:  The stats of the issued metric events 

<a href="../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(processes_diff: int, metric_stats: dict[Type[Event], int]) → None
```










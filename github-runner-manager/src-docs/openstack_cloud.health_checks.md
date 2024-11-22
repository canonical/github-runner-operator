<!-- markdownlint-disable -->

<a href="../../github-runner-manager/src/github_runner_manager/openstack_cloud/health_checks.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `openstack_cloud.health_checks`
Collection of functions related to health checks for a runner VM. 

**Global Variables**
---------------
- **RUNNER_LISTENER_PROCESS**
- **RUNNER_WORKER_PROCESS**
- **INSTANCE_IN_BUILD_MODE_TIMEOUT_IN_HOURS**

---

<a href="../../github-runner-manager/src/github_runner_manager/openstack_cloud/health_checks.py#L29"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `check_runner`

```python
check_runner(
    openstack_cloud: OpenstackCloud,
    instance: OpenstackInstance
) → bool
```

Run a general health check on a runner instance. 

This check applies to runners in any OpenStack state (ACTIVE, STOPPED, etc). 



**Args:**
 
 - <b>`openstack_cloud`</b>:  The OpenstackCloud instance to use 
 - <b>`instance`</b>:  The instance hosting the runner to run health check on. 



**Returns:**
 True if runner is healthy. 


---

<a href="../../github-runner-manager/src/github_runner_manager/openstack_cloud/health_checks.py#L58"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `check_active_runner`

```python
check_active_runner(
    ssh_conn: Connection,
    instance: OpenstackInstance,
    accept_finished_job: bool = False
) → bool
```

Run a health check for a runner whose openstack instance is ACTIVE. 



**Args:**
 
 - <b>`ssh_conn`</b>:  The SSH connection to the runner. 
 - <b>`instance`</b>:  The OpenStack instance to conduit the health check. 
 - <b>`accept_finished_job`</b>:  Whether a job that has finished should be marked healthy.  This is useful for runners in construction whose job has already finished  while the code is still waiting for the runner to be fully operational. Without  the flag, the health check would fail as it checks for running processes  which would not be present in this case. 



**Returns:**
 Whether the runner should be considered healthy. 



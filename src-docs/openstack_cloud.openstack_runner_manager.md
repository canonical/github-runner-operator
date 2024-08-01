<!-- markdownlint-disable -->

<a href="../src/openstack_cloud/openstack_runner_manager.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `openstack_cloud.openstack_runner_manager`




**Global Variables**
---------------
- **BUILD_OPENSTACK_IMAGE_SCRIPT_FILENAME**
- **MAX_METRICS_FILE_SIZE**
- **RUNNER_STARTUP_PROCESS**
- **RUNNER_LISTENER_PROCESS**
- **RUNNER_WORKER_PROCESS**
- **CREATE_SERVER_TIMEOUT**


---

<a href="../src/openstack_cloud/openstack_runner_manager.py#L55"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `OpenstackRunnerManagerConfig`
OpenstackRunnerManagerConfig(image: str, flavor: str, network: str, github_path: charm_state.GithubOrg | charm_state.GithubRepo, labels: list[str], proxy_config: charm_state.ProxyConfig | None, dockerhub_mirror: str | None, ssh_debug_connections: list[charm_state.SSHDebugConnection], repo_policy_url: str, repo_policy_token: str, clouds_config: dict[str, dict], cloud: str) 

<a href="../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    image: str,
    flavor: str,
    network: str,
    github_path: GithubOrg | GithubRepo,
    labels: list[str],
    proxy_config: ProxyConfig | None,
    dockerhub_mirror: str | None,
    ssh_debug_connections: list[SSHDebugConnection],
    repo_policy_url: str,
    repo_policy_token: str,
    clouds_config: dict[str, dict],
    cloud: str
) → None
```









---

<a href="../src/openstack_cloud/openstack_runner_manager.py#L71"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `OpenstackRunnerManager`




<a href="../src/openstack_cloud/openstack_runner_manager.py#L73"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(runner_flavor: str, config: OpenstackRunnerManagerConfig) → None
```








---

<a href="../src/openstack_cloud/openstack_runner_manager.py#L80"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `create_runner`

```python
create_runner(registration_token: str) → str
```





---

<a href="../src/openstack_cloud/openstack_runner_manager.py#L118"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `delete_runners`

```python
delete_runners(id: str, remove_token: str) → None
```





---

<a href="../src/openstack_cloud/openstack_runner_manager.py#L104"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_runner`

```python
get_runner(id: str) → RunnerInstance | None
```





---

<a href="../src/openstack_cloud/openstack_runner_manager.py#L112"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_runners`

```python
get_runners(
    cloud_runner_status: list[CloudRunnerStatus]
) → Tuple[RunnerInstance]
```







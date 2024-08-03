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

<a href="../src/openstack_cloud/openstack_runner_manager.py#L65"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `OpenstackRunnerManagerConfig`
OpenstackRunnerManagerConfig(clouds_config: dict[str, dict], cloud: str, image: str, flavor: str, network: str, github_path: charm_state.GithubOrg | charm_state.GithubRepo, labels: list[str], proxy_config: charm_state.ProxyConfig | None, dockerhub_mirror: str | None, ssh_debug_connections: list[charm_state.SSHDebugConnection] | None, repo_policy_url: str | None, repo_policy_token: str | None) 

<a href="../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    clouds_config: dict[str, dict],
    cloud: str,
    image: str,
    flavor: str,
    network: str,
    github_path: GithubOrg | GithubRepo,
    labels: list[str],
    proxy_config: ProxyConfig | None,
    dockerhub_mirror: str | None,
    ssh_debug_connections: list[SSHDebugConnection] | None,
    repo_policy_url: str | None,
    repo_policy_token: str | None
) → None
```









---

<a href="../src/openstack_cloud/openstack_runner_manager.py#L81"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `OpenstackRunnerManager`




<a href="../src/openstack_cloud/openstack_runner_manager.py#L83"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(prefix: str, config: OpenstackRunnerManagerConfig) → None
```








---

<a href="../src/openstack_cloud/openstack_runner_manager.py#L178"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `cleanup`

```python
cleanup(remove_token: str) → None
```





---

<a href="../src/openstack_cloud/openstack_runner_manager.py#L95"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `create_runner`

```python
create_runner(registration_token: str) → str
```





---

<a href="../src/openstack_cloud/openstack_runner_manager.py#L157"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `delete_runner`

```python
delete_runner(id: str, remove_token: str) → None
```





---

<a href="../src/openstack_cloud/openstack_runner_manager.py#L92"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_name_prefix`

```python
get_name_prefix() → str
```





---

<a href="../src/openstack_cloud/openstack_runner_manager.py#L131"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_runner`

```python
get_runner(id: str) → CloudRunnerInstance | None
```





---

<a href="../src/openstack_cloud/openstack_runner_manager.py#L143"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_runners`

```python
get_runners(
    cloud_runner_status: Sequence[CloudRunnerState]
) → Tuple[CloudRunnerInstance]
```







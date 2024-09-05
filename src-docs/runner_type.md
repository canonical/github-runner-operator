<!-- markdownlint-disable -->

<a href="../src/runner_type.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `runner_type`
Types used by Runner class. 



---

<a href="../src/runner_type.py#L14"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerNameByHealth`
Set of runners instance by health state. 



**Attributes:**
 
 - <b>`healthy`</b>:  Runners that are correctly running runner script. 
 - <b>`unhealthy`</b>:  Runners that are not running runner script. 

<a href="../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(healthy: tuple[str, ], unhealthy: tuple[str, ]) → None
```









---

<a href="../src/runner_type.py#L27"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `ProxySetting`
Represent HTTP-related proxy settings. 



**Attributes:**
 
 - <b>`no_proxy`</b>:  The comma separated URLs to not go through proxy. 
 - <b>`http`</b>:  HTTP proxy URL. 
 - <b>`https`</b>:  HTTPS proxy URL. 
 - <b>`aproxy_address`</b>:  Aproxy URL. 

<a href="../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    no_proxy: Optional[str],
    http: Optional[str],
    https: Optional[str],
    aproxy_address: Optional[str]
) → None
```









---

<a href="../src/runner_type.py#L44"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerConfig`
Configuration for runner. 



**Attributes:**
 
 - <b>`app_name`</b>:  Application name of the charm. 
 - <b>`issue_metrics`</b>:  Whether to issue metrics. 
 - <b>`labels`</b>:  Custom runner labels. 
 - <b>`lxd_storage_path`</b>:  Path to be used as LXD storage. 
 - <b>`name`</b>:  Name of the runner. 
 - <b>`path`</b>:  GitHub repository path in the format '<owner>/<repo>', or the GitHub organization  name. 
 - <b>`proxies`</b>:  HTTP(S) proxy settings. 
 - <b>`dockerhub_mirror`</b>:  URL of dockerhub mirror to use. 
 - <b>`ssh_debug_connections`</b>:  The SSH debug server connections metadata. 

<a href="../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    app_name: str,
    issue_metrics: bool,
    labels: tuple[str],
    lxd_storage_path: Path,
    name: str,
    path: GithubOrg | GithubRepo,
    proxies: ProxySetting,
    dockerhub_mirror: str | None = None,
    ssh_debug_connections: list[SSHDebugConnection] | None = None
) → None
```









---

<a href="../src/runner_type.py#L73"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerStatus`
Status of runner. 



**Attributes:**
 
 - <b>`runner_id`</b>:  ID of the runner. 
 - <b>`exist`</b>:  Whether the runner instance exists on LXD. 
 - <b>`online`</b>:  Whether GitHub marks this runner as online. 
 - <b>`busy`</b>:  Whether GitHub marks this runner as busy. 

<a href="../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    runner_id: Optional[int] = None,
    exist: bool = False,
    online: bool = False,
    busy: bool = False
) → None
```









---

<a href="../src/runner_type.py#L90"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerGithubInfo`
GitHub info of a runner. 



**Attributes:**
 
 - <b>`runner_name`</b>:  Name of the runner. 
 - <b>`runner_id`</b>:  ID of the runner assigned by GitHub. 
 - <b>`online`</b>:  Whether GitHub marks this runner as online. 
 - <b>`busy`</b>:  Whether GitHub marks this runner as busy. 

<a href="../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(runner_name: str, runner_id: int, online: bool, busy: bool) → None
```










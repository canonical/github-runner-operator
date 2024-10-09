<!-- markdownlint-disable -->

<a href="../src/runner_type.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `runner_type.py`
Types used by Runner class. 



---

## <kbd>class</kbd> `ProxySetting`
Represent HTTP-related proxy settings. 



**Attributes:**
 
 - <b>`no_proxy`</b>:  The comma separated URLs to not go through proxy. 
 - <b>`http`</b>:  HTTP proxy URL. 
 - <b>`https`</b>:  HTTPS proxy URL. 
 - <b>`aproxy_address`</b>:  Aproxy URL. 





---

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





---

## <kbd>class</kbd> `RunnerGithubInfo`
GitHub info of a runner. 



**Attributes:**
 
 - <b>`runner_name`</b>:  Name of the runner. 
 - <b>`runner_id`</b>:  ID of the runner assigned by GitHub. 
 - <b>`online`</b>:  Whether GitHub marks this runner as online. 
 - <b>`busy`</b>:  Whether GitHub marks this runner as busy. 





---

## <kbd>class</kbd> `RunnerNameByHealth`
Set of runners instance by health state. 



**Attributes:**
 
 - <b>`healthy`</b>:  Runners that are correctly running runner script. 
 - <b>`unhealthy`</b>:  Runners that are not running runner script. 





---

## <kbd>class</kbd> `RunnerStatus`
Status of runner. 



**Attributes:**
 
 - <b>`runner_id`</b>:  ID of the runner. 
 - <b>`exist`</b>:  Whether the runner instance exists on LXD. 
 - <b>`online`</b>:  Whether GitHub marks this runner as online. 
 - <b>`busy`</b>:  Whether GitHub marks this runner as busy. 






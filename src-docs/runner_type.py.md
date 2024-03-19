<!-- markdownlint-disable -->

<a href="../src/runner_type.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `runner_type.py`
Types used by Runner class. 



---

## <kbd>class</kbd> `ProxySetting`
Represent HTTP-related proxy settings. 





---

## <kbd>class</kbd> `RunnerByHealth`
Set of runners LXD instance by health state. 





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

## <kbd>class</kbd> `RunnerStatus`
Status of runner. 



**Attributes:**
 
 - <b>`runner_id`</b>:  ID of the runner. 
 - <b>`exist`</b>:  Whether the runner instance exists on LXD. 
 - <b>`online`</b>:  Whether GitHub marks this runner as online. 
 - <b>`busy`</b>:  Whether GitHub marks this runner as busy. 






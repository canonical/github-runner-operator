<!-- markdownlint-disable -->

<a href="../../github-runner-manager/src/cli_config.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `cli_config.py`
The configuration file processing for the CLI. 



---

## <kbd>class</kbd> `Configuration`
Configuration for github-runner-manager application. 



**Attributes:**
 
 - <b>`name`</b>:  A name for this github-runner-manager instance. 
 - <b>`github_path`</b>:  The GitHub path to register the runners. 
 - <b>`github_token`</b>:  The GitHub Personal Access Token (PAT) to register the runners. 
 - <b>`github_runner_group`</b>:  The runner group to register runners for GitHub organization. Ignored  if the runner is registered to GitHub repository. Defaults to None. 
 - <b>`runner_count`</b>:  The desired number of self-hosted runners. 
 - <b>`runner_labels`</b>:  The labels  
 - <b>`openstack_auth_url`</b>:  The address of the openstack host. 
 - <b>`openstack_project_name`</b>:  The openstack project name. 
 - <b>`openstack_username`</b>:  The username for login to the openstack project. 
 - <b>`openstack_password`</b>:  The password for login to the openstack project. 
 - <b>`openstack_user_domain_name`</b>:  The domain name for the openstack user. 
 - <b>`openstack_domain_name`</b>:  The domain name for the openstack project. 
 - <b>`openstack_flavor`</b>:  The openstack flavor to spawn virtual machine for runners. 
 - <b>`openstack_network`</b>:  The openstack network to spawn virtual machine for runners. 
 - <b>`dockerhub_mirror`</b>:  The optional docker registry as dockerhub mirror for the runners to use.   Defaults to None. 
 - <b>`repo_policy_compliance_url`</b>:  The optional repo-policy-compliance address. Defaults to None. 
 - <b>`repo_policy_compliance_token`</b>:  The token to query the repo-policy-compliance. Defaults to   None. 
 - <b>`enable_aproxy`</b>:  Whether to use aproxy for automatic redirect traffic to HTTP(S) proxy.   Defaults to True. 




---

<a href="../../github-runner-manager/src/cli_config.py#L58"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `from_yaml_file`

```python
from_yaml_file(file: <class 'TextIO'>) → Configuration
```

Initialize configuration from a YAML formatted file. 



**Args:**
 
 - <b>`file`</b>:  The file object to parse the configuration from. 



**Returns:**
 The configuration. 



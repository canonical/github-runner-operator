<!-- markdownlint-disable -->

<a href="../src/runner_manager_type.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `runner_manager_type.py`
Types used by RunnerManager class. 



---

## <kbd>class</kbd> `FlushMode`
Strategy for flushing runners. 



**Attributes:**
 
 - <b>`FLUSH_IDLE`</b>:  Flush only idle runners. 
 - <b>`FLUSH_IDLE_WAIT_REPO_CHECK`</b>:  Flush only idle runners, then wait until repo-policy-check is  completed for the busy runners. 
 - <b>`FORCE_FLUSH_BUSY`</b>:  Force flush busy runners. 
 - <b>`FORCE_FLUSH_BUSY_WAIT_REPO_CHECK`</b>:  Wait until the repo-policy-check is completed before  force flush of busy runners. 





---

## <kbd>class</kbd> `RunnerInfo`
Information from GitHub of a runner. 

Used as a returned type to method querying runner information. 



**Attributes:**
 
 - <b>`name`</b>:  Name of the runner. 
 - <b>`status`</b>:  Status of the runner. 
 - <b>`busy`</b>:  Whether the runner has taken a job. 





---

## <kbd>class</kbd> `RunnerManagerClients`
Clients for accessing various services. 



**Attributes:**
 
 - <b>`github`</b>:  Used to query GitHub API. 
 - <b>`jinja`</b>:  Used for templating. 
 - <b>`lxd`</b>:  Used to interact with LXD API. 





---

## <kbd>class</kbd> `RunnerManagerConfig`
Configuration of runner manager. 



**Attributes:**
 
 - <b>`path`</b>:  GitHub repository path in the format '<owner>/<repo>', or the  GitHub organization name. 
 - <b>`token`</b>:  GitHub personal access token to register runner to the  repository or organization. 
 - <b>`image`</b>:  Name of the image for creating LXD instance. 
 - <b>`service_token`</b>:  Token for accessing local service. 
 - <b>`lxd_storage_path`</b>:  Path to be used as LXD storage. 
 - <b>`charm_state`</b>:  The state of the charm. 
 - <b>`dockerhub_mirror`</b>:  URL of dockerhub mirror to use. 


---

#### <kbd>property</kbd> are_metrics_enabled

Whether metrics for the runners should be collected. 





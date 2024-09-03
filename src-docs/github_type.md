<!-- markdownlint-disable -->

<a href="../src/github_type.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `github_type`
Return type for the GitHub web API. 



---

<a href="../src/github_type.py#L17"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `GitHubRunnerStatus`
Status of runner on GitHub. 



**Attributes:**
 
 - <b>`ONLINE`</b>:  Represents an online runner status. 
 - <b>`OFFLINE`</b>:  Represents an offline runner status. 





---

<a href="../src/github_type.py#L31"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RunnerApplication`
Information on the runner application. 



**Attributes:**
 
 - <b>`os`</b>:  Operating system to run the runner application on. 
 - <b>`architecture`</b>:  Computer Architecture to run the runner application on. 
 - <b>`download_url`</b>:  URL to download the runner application. 
 - <b>`filename`</b>:  Filename of the runner application. 
 - <b>`temp_download_token`</b>:  A short lived bearer token used to download the  runner, if needed. 
 - <b>`sha256_checksum`</b>:  SHA256 Checksum of the runner application. 





---

<a href="../src/github_type.py#L55"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `SelfHostedRunnerLabel`
A single label of self-hosted runners. 



**Attributes:**
 
 - <b>`id`</b>:  Unique identifier of the label. 
 - <b>`name`</b>:  Name of the label. 
 - <b>`type`</b>:  Type of label. Read-only labels are applied automatically when  the runner is configured. 





---

<a href="../src/github_type.py#L70"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `SelfHostedRunner`
Information on a single self-hosted runner. 



**Attributes:**
 
 - <b>`busy`</b>:  Whether the runner is executing a job. 
 - <b>`id`</b>:  Unique identifier of the runner. 
 - <b>`labels`</b>:  Labels of the runner. 
 - <b>`os`</b>:  Operation system of the runner. 
 - <b>`name`</b>:  Name of the runner. 
 - <b>`status`</b>:  The Github runner status. 





---

<a href="../src/github_type.py#L90"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `SelfHostedRunnerList`
Information on a collection of self-hosted runners. 



**Attributes:**
 
 - <b>`total_count`</b>:  Total number of runners. 
 - <b>`runners`</b>:  List of runners. 





---

<a href="../src/github_type.py#L102"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RegistrationToken`
Token used for registering GitHub runners. 



**Attributes:**
 
 - <b>`token`</b>:  Token for registering GitHub runners. 
 - <b>`expires_at`</b>:  Time the token expires at. 





---

<a href="../src/github_type.py#L114"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `RemoveToken`
Token used for removing GitHub runners. 



**Attributes:**
 
 - <b>`token`</b>:  Token for removing GitHub runners. 
 - <b>`expires_at`</b>:  Time the token expires at. 





---

<a href="../src/github_type.py#L126"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `JobConclusion`
Conclusion of a job on GitHub. 

See :https://docs.github.com/en/rest/actions/workflow-runs?apiVersion=2022-11-28#list-workflow-runs-for-a-repository 



**Attributes:**
 
 - <b>`ACTION_REQUIRED`</b>:  Represents additional action required on the job. 
 - <b>`CANCELLED`</b>:  Represents a cancelled job status. 
 - <b>`FAILURE`</b>:  Represents a failed job status. 
 - <b>`NEUTRAL`</b>:  Represents a job status that can optionally succeed or fail. 
 - <b>`SKIPPED`</b>:  Represents a skipped job status. 
 - <b>`SUCCESS`</b>:  Represents a successful job status. 
 - <b>`TIMED_OUT`</b>:  Represents a job that has timed out. 





---

<a href="../src/github_type.py#L151"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `JobStats`
Stats for a job on GitHub. 



**Attributes:**
 
 - <b>`job_id`</b>:  The ID of the job. 
 - <b>`created_at`</b>:  The time the job was created. 
 - <b>`started_at`</b>:  The time the job was started. 
 - <b>`conclusion`</b>:  The end result of a job. 


---

#### <kbd>property</kbd> model_extra

Get extra fields set during validation. 



**Returns:**
  A dictionary of extra fields, or `None` if `config.extra` is not set to `"allow"`. 

---

#### <kbd>property</kbd> model_fields_set

Returns the set of fields that have been explicitly set on this model instance. 



**Returns:**
  A set of strings representing the fields that have been set,  i.e. that were not filled from defaults. 





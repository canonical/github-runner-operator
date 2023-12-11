<!-- markdownlint-disable -->

<a href="../src/github_type.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `github_type.py`
Return type for the GitHub web API. 



---

## <kbd>class</kbd> `GitHubRunnerStatus`
Status of runner on GitHub. 





---

## <kbd>class</kbd> `GithubJobStats`
Stats for a job on GitHub. 

Attributes  created_at: The time the job was created.  started_at: The time the job was started. 





---

## <kbd>class</kbd> `RegistrationToken`
Token used for registering GitHub runners. 



**Attributes:**
 
 - <b>`token`</b>:  Token for registering GitHub runners. 
 - <b>`expires_at`</b>:  Time the token expires at. 





---

## <kbd>class</kbd> `RemoveToken`
Token used for removing GitHub runners. 



**Attributes:**
 
 - <b>`token`</b>:  Token for removing GitHub runners. 
 - <b>`expires_at`</b>:  Time the token expires at. 





---

## <kbd>class</kbd> `RunnerApplication`
Information on the runner application. 



**Attributes:**
 
 - <b>`os`</b>:  Operating system to run the runner application on. 
 - <b>`architecture`</b>:  Computer Architecture to run the runner application on. 
 - <b>`download_url`</b>:  URL to download the runner application. 
 - <b>`filename`</b>:  Filename of the runner application. 
 - <b>`temp_download_token`</b>:  A short lived bearer token used to download the  runner, if needed. 
 - <b>`sha256_check_sum`</b>:  SHA256 Checksum of the runner application. 





---

## <kbd>class</kbd> `SelfHostedRunner`
Information on a single self-hosted runner. 



**Attributes:**
 
 - <b>`id`</b>:  Unique identifier of the runner. 
 - <b>`name`</b>:  Name of the runner. 
 - <b>`os`</b>:  Operation system of the runner. 
 - <b>`busy`</b>:  Whether the runner is executing a job. 
 - <b>`labels`</b>:  Labels of the runner. 





---

## <kbd>class</kbd> `SelfHostedRunnerLabel`
A single label of self-hosted runners. 



**Attributes:**
 
 - <b>`id`</b>:  Unique identifier of the label. 
 - <b>`name`</b>:  Name of the label. 
 - <b>`type`</b>:  Type of label. Read-only labels are applied automatically when  the runner is configured. 





---

## <kbd>class</kbd> `SelfHostedRunnerList`
Information on a collection of self-hosted runners. 



**Attributes:**
 
 - <b>`total_count`</b>:  Total number of runners. 
 - <b>`runners`</b>:  List of runners. 






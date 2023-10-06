<!-- markdownlint-disable -->

<a href="../src/github_type.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `github_type.py`
Return type for the GitHub web API. 



---

## <kbd>class</kbd> `GitHubRunnerStatus`
Status of runner on GitHub. 





---

## <kbd>class</kbd> `RegistrationToken`
Token used for registering GitHub runners. 

Attrs:  token: Token for registering GitHub runners.  expires_at: Time the token expires at. 





---

## <kbd>class</kbd> `RemoveToken`
Token used for removing GitHub runners. 

Attrs:  token: Token for removing GitHub runners.  expires_at: Time the token expires at. 





---

## <kbd>class</kbd> `RunnerApplication`
Information on the runner application. 

Attrs:  os: Operating system to run the runner application on.  architecture: Computer Architecture to run the runner application on.  download_url: URL to download the runner application.  filename: Filename of the runner application.  temp_download_token: A short lived bearer token used to download the  runner, if needed.  sha256_check_sum: SHA256 Checksum of the runner application. 





---

## <kbd>class</kbd> `SelfHostedRunner`
Information on a single self-hosted runner. 

Attrs:  id: Unique identifier of the runner.  name: Name of the runner.  os: Operation system of the runner.  busy: Whether the runner is executing a job.  labels: Labels of the runner. 





---

## <kbd>class</kbd> `SelfHostedRunnerLabel`
A single label of self-hosted runners. 

Attrs:  id: Unique identifier of the label.  name: Name of the label.  type: Type of label. Read-only labels are applied automatically when  the runner is configured. 





---

## <kbd>class</kbd> `SelfHostedRunnerList`
Information on a collection of self-hosted runners. 

Attrs:  total_count: Total number of runners.  runners: List of runners. 






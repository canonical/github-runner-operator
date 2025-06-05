# RegisterRunnerV1RunnerRegisterPostRequest


## Properties
Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**name** | **str** |  | 
**series** | **str** |  | 
**arch** | **str** |  | 
**labels** | **List[str]** |  | [optional] 
**vm_size** | **str** |  | [optional] 

## Example

```python
from jobmanager_client.models.register_runner_v1_runner_register_post_request import RegisterRunnerV1RunnerRegisterPostRequest

# TODO update the JSON string below
json = "{}"
# create an instance of RegisterRunnerV1RunnerRegisterPostRequest from a JSON string
register_runner_v1_runner_register_post_request_instance = RegisterRunnerV1RunnerRegisterPostRequest.from_json(json)
# print the JSON string representation of the object
print RegisterRunnerV1RunnerRegisterPostRequest.to_json()

# convert the object into a dict
register_runner_v1_runner_register_post_request_dict = register_runner_v1_runner_register_post_request_instance.to_dict()
# create an instance of RegisterRunnerV1RunnerRegisterPostRequest from a dict
register_runner_v1_runner_register_post_request_from_dict = RegisterRunnerV1RunnerRegisterPostRequest.from_dict(register_runner_v1_runner_register_post_request_dict)
```
[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)



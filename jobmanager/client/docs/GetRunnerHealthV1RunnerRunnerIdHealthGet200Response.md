# GetRunnerHealthV1RunnerRunnerIdHealthGet200Response


## Properties
Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**label** | **str** |  | [optional] 
**cpu_usage** | **str** |  | [optional] 
**ram_usage** | **str** |  | [optional] 
**disk_usage** | **str** |  | [optional] 
**status** | **str** |  | [optional] 
**deletable** | **bool** |  | [optional] 

## Example

```python
from jobmanager_client.models.get_runner_health_v1_runner_runner_id_health_get200_response import GetRunnerHealthV1RunnerRunnerIdHealthGet200Response

# TODO update the JSON string below
json = "{}"
# create an instance of GetRunnerHealthV1RunnerRunnerIdHealthGet200Response from a JSON string
get_runner_health_v1_runner_runner_id_health_get200_response_instance = GetRunnerHealthV1RunnerRunnerIdHealthGet200Response.from_json(json)
# print the JSON string representation of the object
print GetRunnerHealthV1RunnerRunnerIdHealthGet200Response.to_json()

# convert the object into a dict
get_runner_health_v1_runner_runner_id_health_get200_response_dict = get_runner_health_v1_runner_runner_id_health_get200_response_instance.to_dict()
# create an instance of GetRunnerHealthV1RunnerRunnerIdHealthGet200Response from a dict
get_runner_health_v1_runner_runner_id_health_get200_response_from_dict = GetRunnerHealthV1RunnerRunnerIdHealthGet200Response.from_dict(get_runner_health_v1_runner_runner_id_health_get200_response_dict)
```
[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)



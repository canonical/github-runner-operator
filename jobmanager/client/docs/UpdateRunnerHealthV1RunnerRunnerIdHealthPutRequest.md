# UpdateRunnerHealthV1RunnerRunnerIdHealthPutRequest


## Properties
Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**label** | **str** |  | 
**cpu_usage** | **str** |  | 
**ram_usage** | **str** |  | 
**disk_usage** | **str** |  | 
**status** | **str** |  | 

## Example

```python
from jobmanager_client.models.update_runner_health_v1_runner_runner_id_health_put_request import UpdateRunnerHealthV1RunnerRunnerIdHealthPutRequest

# TODO update the JSON string below
json = "{}"
# create an instance of UpdateRunnerHealthV1RunnerRunnerIdHealthPutRequest from a JSON string
update_runner_health_v1_runner_runner_id_health_put_request_instance = UpdateRunnerHealthV1RunnerRunnerIdHealthPutRequest.from_json(json)
# print the JSON string representation of the object
print UpdateRunnerHealthV1RunnerRunnerIdHealthPutRequest.to_json()

# convert the object into a dict
update_runner_health_v1_runner_runner_id_health_put_request_dict = update_runner_health_v1_runner_runner_id_health_put_request_instance.to_dict()
# create an instance of UpdateRunnerHealthV1RunnerRunnerIdHealthPutRequest from a dict
update_runner_health_v1_runner_runner_id_health_put_request_from_dict = UpdateRunnerHealthV1RunnerRunnerIdHealthPutRequest.from_dict(update_runner_health_v1_runner_runner_id_health_put_request_dict)
```
[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)



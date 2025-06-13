# JobUpdate

Job update model.

## Properties
Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**status** | **str** |  | [optional] 
**vm_ip** | **str** |  | [optional] 
**artifact_urls** | **List[object]** |  | [optional] 
**log_urls** | **List[object]** |  | [optional] 
**started_at** | **datetime** |  | [optional] 
**completed_at** | **datetime** |  | [optional] 

## Example

```python
from jobmanager_client.models.job_update import JobUpdate

# TODO update the JSON string below
json = "{}"
# create an instance of JobUpdate from a JSON string
job_update_instance = JobUpdate.from_json(json)
# print the JSON string representation of the object
print JobUpdate.to_json()

# convert the object into a dict
job_update_dict = job_update_instance.to_dict()
# create an instance of JobUpdate from a dict
job_update_from_dict = JobUpdate.from_dict(job_update_dict)
```
[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)



# JobCreate

Job creation model.

## Properties
Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**requested_by** | **str** |  | 
**repository_url** | **str** |  | [optional] 
**repository_ref** | **str** |  | [optional] 
**architecture** | **str** |  | 
**base_series** | **str** |  | 
**vm_dependencies** | [**VmDependencies**](VmDependencies.md) |  | [optional] 
**commands** | **List[object]** |  | [optional] 
**secrets** | **Dict[str, object]** |  | [optional] 
**environment** | **Dict[str, object]** |  | [optional] 
**artifacts_dir** | **str** |  | [optional] 
**topology** | **str** |  | [optional] 
**vm_ip** | **str** |  | [optional] 
**vm_size** | **str** |  | [optional] 
**status** | **str** |  | [optional] 
**artifact_urls** | **List[object]** |  | [optional] 
**log_urls** | **List[object]** |  | [optional] 

## Example

```python
from jobmanager_client.models.job_create import JobCreate

# TODO update the JSON string below
json = "{}"
# create an instance of JobCreate from a JSON string
job_create_instance = JobCreate.from_json(json)
# print the JSON string representation of the object
print JobCreate.to_json()

# convert the object into a dict
job_create_dict = job_create_instance.to_dict()
# create an instance of JobCreate from a dict
job_create_from_dict = JobCreate.from_dict(job_create_dict)
```
[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)



# Job


## Properties
Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**job_id** | **int** |  | [optional] 
**requested_by** | **str** |  | [optional] 
**repository_url** | **str** |  | [optional] 
**repository_ref** | **str** |  | [optional] 
**architecture** | **str** |  | [optional] 
**base_series** | **str** |  | [optional] 
**vm_dependencies** | **object** |  | [optional] 
**commands** | **List[str]** |  | [optional] 
**secrets** | **object** |  | [optional] 
**environment** | **object** |  | [optional] 
**artifacts_dir** | **str** |  | [optional] 
**topology** | **str** |  | [optional] 
**vm_ip** | **str** |  | [optional] 
**vm_size** | **str** |  | [optional] 
**status** | **str** |  | [optional] 
**artifact_urls** | **List[str]** |  | [optional] 
**log_url** | **str** |  | [optional] 
**created_at** | **datetime** |  | [optional] 
**updated_at** | **datetime** |  | [optional] 
**started_at** | **datetime** |  | [optional] 
**completed_at** | **datetime** |  | [optional] 

## Example

```python
from jobmanager_client.models.job import Job

# TODO update the JSON string below
json = "{}"
# create an instance of Job from a JSON string
job_instance = Job.from_json(json)
# print the JSON string representation of the object
print Job.to_json()

# convert the object into a dict
job_dict = job_instance.to_dict()
# create an instance of Job from a dict
job_from_dict = Job.from_dict(job_dict)
```
[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)



# V1JobsJobIdHealthGet200Response


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
from jobmanager_client.models.v1_jobs_job_id_health_get200_response import V1JobsJobIdHealthGet200Response

# TODO update the JSON string below
json = "{}"
# create an instance of V1JobsJobIdHealthGet200Response from a JSON string
v1_jobs_job_id_health_get200_response_instance = V1JobsJobIdHealthGet200Response.from_json(json)
# print the JSON string representation of the object
print V1JobsJobIdHealthGet200Response.to_json()

# convert the object into a dict
v1_jobs_job_id_health_get200_response_dict = v1_jobs_job_id_health_get200_response_instance.to_dict()
# create an instance of V1JobsJobIdHealthGet200Response from a dict
v1_jobs_job_id_health_get200_response_from_dict = V1JobsJobIdHealthGet200Response.from_dict(v1_jobs_job_id_health_get200_response_dict)
```
[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)



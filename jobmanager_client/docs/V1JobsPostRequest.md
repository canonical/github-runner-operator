# V1JobsPostRequest


## Properties
Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**repository_url** | **str** |  | [optional] 
**repository_ref** | **str** |  | [optional] 
**architecture** | **str** |  | [optional] 
**vm_dependecies** | **object** |  | [optional] 
**commands** | **List[str]** |  | [optional] 
**secrets** | **object** |  | [optional] 
**environment** | **object** |  | [optional] 
**artifacts_dir** | **str** |  | [optional] 
**topology** | **str** |  | [optional] 
**vm_size** | **str** |  | [optional] 

## Example

```python
from jobmanager_client.models.v1_jobs_post_request import V1JobsPostRequest

# TODO update the JSON string below
json = "{}"
# create an instance of V1JobsPostRequest from a JSON string
v1_jobs_post_request_instance = V1JobsPostRequest.from_json(json)
# print the JSON string representation of the object
print V1JobsPostRequest.to_json()

# convert the object into a dict
v1_jobs_post_request_dict = v1_jobs_post_request_instance.to_dict()
# create an instance of V1JobsPostRequest from a dict
v1_jobs_post_request_from_dict = V1JobsPostRequest.from_dict(v1_jobs_post_request_dict)
```
[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)



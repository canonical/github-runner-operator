# V1JobsJobIdTokenPostRequest


## Properties
Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**public_key** | **str** |  | [optional] 
**private_key** | **str** |  | [optional] 
**job_id** | **int** |  | [optional] 

## Example

```python
from jobmanager_client.models.v1_jobs_job_id_token_post_request import V1JobsJobIdTokenPostRequest

# TODO update the JSON string below
json = "{}"
# create an instance of V1JobsJobIdTokenPostRequest from a JSON string
v1_jobs_job_id_token_post_request_instance = V1JobsJobIdTokenPostRequest.from_json(json)
# print the JSON string representation of the object
print V1JobsJobIdTokenPostRequest.to_json()

# convert the object into a dict
v1_jobs_job_id_token_post_request_dict = v1_jobs_job_id_token_post_request_instance.to_dict()
# create an instance of V1JobsJobIdTokenPostRequest from a dict
v1_jobs_job_id_token_post_request_from_dict = V1JobsJobIdTokenPostRequest.from_dict(v1_jobs_job_id_token_post_request_dict)
```
[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)



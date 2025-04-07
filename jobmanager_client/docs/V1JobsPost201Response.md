# V1JobsPost201Response


## Properties
Name | Type | Description | Notes
------------ | ------------- | ------------- | -------------
**status_url** | **str** |  | [optional] 
**maintenance** | [**V1JobsPost201ResponseMaintenance**](V1JobsPost201ResponseMaintenance.md) |  | [optional] 

## Example

```python
from jobmanager_client.models.v1_jobs_post201_response import V1JobsPost201Response

# TODO update the JSON string below
json = "{}"
# create an instance of V1JobsPost201Response from a JSON string
v1_jobs_post201_response_instance = V1JobsPost201Response.from_json(json)
# print the JSON string representation of the object
print V1JobsPost201Response.to_json()

# convert the object into a dict
v1_jobs_post201_response_dict = v1_jobs_post201_response_instance.to_dict()
# create an instance of V1JobsPost201Response from a dict
v1_jobs_post201_response_from_dict = V1JobsPost201Response.from_dict(v1_jobs_post201_response_dict)
```
[[Back to Model list]](../README.md#documentation-for-models) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to README]](../README.md)



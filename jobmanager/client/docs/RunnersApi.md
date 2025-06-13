# jobmanager_client.RunnersApi

All URIs are relative to *http://localhost*

Method | HTTP request | Description
------------- | ------------- | -------------
[**get_runner_health_v1_runner_runner_id_health_get**](RunnersApi.md#get_runner_health_v1_runner_runner_id_health_get) | **GET** /v1/runner/{runner_id}/health | Get Runner Health
[**register_runner_v1_runner_register_post**](RunnersApi.md#register_runner_v1_runner_register_post) | **POST** /v1/runner/register | Register Runner
[**update_runner_health_v1_runner_runner_id_health_put**](RunnersApi.md#update_runner_health_v1_runner_runner_id_health_put) | **PUT** /v1/runner/{runner_id}/health | Update Runner Health


# **get_runner_health_v1_runner_runner_id_health_get**
> GetRunnerHealthV1RunnerRunnerIdHealthGet200Response get_runner_health_v1_runner_runner_id_health_get(runner_id)

Get Runner Health

This endpoint is used by the Builder Manager to ask for builder status.

### Example

* Basic Authentication (APIAccessToken):
```python
import time
import os
import jobmanager_client
from jobmanager_client.models.get_runner_health_v1_runner_runner_id_health_get200_response import GetRunnerHealthV1RunnerRunnerIdHealthGet200Response
from jobmanager_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://localhost
# See configuration.py for a list of all supported configuration parameters.
configuration = jobmanager_client.Configuration(
    host = "http://localhost"
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

# Configure HTTP basic authorization: APIAccessToken
configuration = jobmanager_client.Configuration(
    username = os.environ["USERNAME"],
    password = os.environ["PASSWORD"]
)

# Enter a context with an instance of the API client
with jobmanager_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = jobmanager_client.RunnersApi(api_client)
    runner_id = 56 # int | Runner ID that can be used to retrieve the builder status

    try:
        # Get Runner Health
        api_response = api_instance.get_runner_health_v1_runner_runner_id_health_get(runner_id)
        print("The response of RunnersApi->get_runner_health_v1_runner_runner_id_health_get:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling RunnersApi->get_runner_health_v1_runner_runner_id_health_get: %s\n" % e)
```



### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **runner_id** | **int**| Runner ID that can be used to retrieve the builder status | 

### Return type

[**GetRunnerHealthV1RunnerRunnerIdHealthGet200Response**](GetRunnerHealthV1RunnerRunnerIdHealthGet200Response.md)

### Authorization

[APIAccessToken](../README.md#APIAccessToken)

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Successful Response |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **register_runner_v1_runner_register_post**
> RegisterRunnerV1RunnerRegisterPost200Response register_runner_v1_runner_register_post(register_runner_v1_runner_register_post_request)

Register Runner

This endpoint is used by the Builder Manager to register a new runner. It sends metadata and its current capabilities so it can be tracked and assigned jobs.

### Example

* Basic Authentication (APIAccessToken):
```python
import time
import os
import jobmanager_client
from jobmanager_client.models.register_runner_v1_runner_register_post200_response import RegisterRunnerV1RunnerRegisterPost200Response
from jobmanager_client.models.register_runner_v1_runner_register_post_request import RegisterRunnerV1RunnerRegisterPostRequest
from jobmanager_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://localhost
# See configuration.py for a list of all supported configuration parameters.
configuration = jobmanager_client.Configuration(
    host = "http://localhost"
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

# Configure HTTP basic authorization: APIAccessToken
configuration = jobmanager_client.Configuration(
    username = os.environ["USERNAME"],
    password = os.environ["PASSWORD"]
)

# Enter a context with an instance of the API client
with jobmanager_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = jobmanager_client.RunnersApi(api_client)
    register_runner_v1_runner_register_post_request = jobmanager_client.RegisterRunnerV1RunnerRegisterPostRequest() # RegisterRunnerV1RunnerRegisterPostRequest | 

    try:
        # Register Runner
        api_response = api_instance.register_runner_v1_runner_register_post(register_runner_v1_runner_register_post_request)
        print("The response of RunnersApi->register_runner_v1_runner_register_post:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling RunnersApi->register_runner_v1_runner_register_post: %s\n" % e)
```



### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **register_runner_v1_runner_register_post_request** | [**RegisterRunnerV1RunnerRegisterPostRequest**](RegisterRunnerV1RunnerRegisterPostRequest.md)|  | 

### Return type

[**RegisterRunnerV1RunnerRegisterPost200Response**](RegisterRunnerV1RunnerRegisterPost200Response.md)

### Authorization

[APIAccessToken](../README.md#APIAccessToken)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Successful Response |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **update_runner_health_v1_runner_runner_id_health_put**
> object update_runner_health_v1_runner_runner_id_health_put(runner_id, update_runner_health_v1_runner_runner_id_health_put_request)

Update Runner Health

This endpoint is used by Builder Agent (on a builder) to send to the Job Manager their health checks.

### Example

* Basic Authentication (BuilderToken):
```python
import time
import os
import jobmanager_client
from jobmanager_client.models.update_runner_health_v1_runner_runner_id_health_put_request import UpdateRunnerHealthV1RunnerRunnerIdHealthPutRequest
from jobmanager_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://localhost
# See configuration.py for a list of all supported configuration parameters.
configuration = jobmanager_client.Configuration(
    host = "http://localhost"
)

# The client must configure the authentication and authorization parameters
# in accordance with the API server security policy.
# Examples for each auth method are provided below, use the example that
# satisfies your auth use case.

# Configure HTTP basic authorization: BuilderToken
configuration = jobmanager_client.Configuration(
    username = os.environ["USERNAME"],
    password = os.environ["PASSWORD"]
)

# Enter a context with an instance of the API client
with jobmanager_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = jobmanager_client.RunnersApi(api_client)
    runner_id = 56 # int | Runner ID that can be used to update the builder health status
    update_runner_health_v1_runner_runner_id_health_put_request = jobmanager_client.UpdateRunnerHealthV1RunnerRunnerIdHealthPutRequest() # UpdateRunnerHealthV1RunnerRunnerIdHealthPutRequest | 

    try:
        # Update Runner Health
        api_response = api_instance.update_runner_health_v1_runner_runner_id_health_put(runner_id, update_runner_health_v1_runner_runner_id_health_put_request)
        print("The response of RunnersApi->update_runner_health_v1_runner_runner_id_health_put:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling RunnersApi->update_runner_health_v1_runner_runner_id_health_put: %s\n" % e)
```



### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **runner_id** | **int**| Runner ID that can be used to update the builder health status | 
 **update_runner_health_v1_runner_runner_id_health_put_request** | [**UpdateRunnerHealthV1RunnerRunnerIdHealthPutRequest**](UpdateRunnerHealthV1RunnerRunnerIdHealthPutRequest.md)|  | 

### Return type

**object**

### Authorization

[BuilderToken](../README.md#BuilderToken)

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Successful Response |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)


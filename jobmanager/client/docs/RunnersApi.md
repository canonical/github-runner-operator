# jobmanager_client.RunnersApi

All URIs are relative to *http://localhost*

Method | HTTP request | Description
------------- | ------------- | -------------
[**get_runner_health_v1_runners_runner_id_health_get**](RunnersApi.md#get_runner_health_v1_runners_runner_id_health_get) | **GET** /v1/runners/{runner_id}/health | Get Runner Health
[**register_runner_v1_runners_register_post**](RunnersApi.md#register_runner_v1_runners_register_post) | **POST** /v1/runners/register | Register Runner
[**update_runner_health_v1_runners_runner_id_health_put**](RunnersApi.md#update_runner_health_v1_runners_runner_id_health_put) | **PUT** /v1/runners/{runner_id}/health | Update Runner Health


# **get_runner_health_v1_runners_runner_id_health_get**
> RunnerHealthResponse get_runner_health_v1_runners_runner_id_health_get(runner_id)

Get Runner Health

Get runner health status.

Args:
    runner_id: Unique identifier of the runner
    db: Database session dependency

Returns:
    dict: Runner health metrics including CPU, RAM, disk usage and status

Raises:
    HTTPException 404: If runner is not found

### Example

```python
import time
import os
import jobmanager_client
from jobmanager_client.models.runner_health_response import RunnerHealthResponse
from jobmanager_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://localhost
# See configuration.py for a list of all supported configuration parameters.
configuration = jobmanager_client.Configuration(
    host = "http://localhost"
)


# Enter a context with an instance of the API client
with jobmanager_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = jobmanager_client.RunnersApi(api_client)
    runner_id = 56 # int | 

    try:
        # Get Runner Health
        api_response = api_instance.get_runner_health_v1_runners_runner_id_health_get(runner_id)
        print("The response of RunnersApi->get_runner_health_v1_runners_runner_id_health_get:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling RunnersApi->get_runner_health_v1_runners_runner_id_health_get: %s\n" % e)
```



### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **runner_id** | **int**|  | 

### Return type

[**RunnerHealthResponse**](RunnerHealthResponse.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Successful Response |  -  |
**422** | Validation Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **register_runner_v1_runners_register_post**
> RunnerRegisterResponse register_runner_v1_runners_register_post(runner_create)

Register Runner

Register a new runner.

Args:
    runner_in: Runner registration data including name and labels
    db: Database session dependency
    token: API access token for authorization

Returns:
    dict: Contains the runner ID and its authentication token

Raises:
    HTTPException 500: If token generation fails

### Example

```python
import time
import os
import jobmanager_client
from jobmanager_client.models.runner_create import RunnerCreate
from jobmanager_client.models.runner_register_response import RunnerRegisterResponse
from jobmanager_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://localhost
# See configuration.py for a list of all supported configuration parameters.
configuration = jobmanager_client.Configuration(
    host = "http://localhost"
)


# Enter a context with an instance of the API client
with jobmanager_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = jobmanager_client.RunnersApi(api_client)
    runner_create = jobmanager_client.RunnerCreate() # RunnerCreate | 

    try:
        # Register Runner
        api_response = api_instance.register_runner_v1_runners_register_post(runner_create)
        print("The response of RunnersApi->register_runner_v1_runners_register_post:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling RunnersApi->register_runner_v1_runners_register_post: %s\n" % e)
```



### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **runner_create** | [**RunnerCreate**](RunnerCreate.md)|  | 

### Return type

[**RunnerRegisterResponse**](RunnerRegisterResponse.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Successful Response |  -  |
**422** | Validation Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **update_runner_health_v1_runners_runner_id_health_put**
> RunnerHealthUpdateResponse update_runner_health_v1_runners_runner_id_health_put(runner_id)

Update Runner Health

Update runner health metrics.

Args:
    runner_id: Unique identifier of the runner
    request: FastAPI request object containing health metrics
    db: Database session dependency
    token: Runner token for authorization

Returns:
    dict: Success indicator

Raises:
    HTTPException 404: If runner is not found

### Example

```python
import time
import os
import jobmanager_client
from jobmanager_client.models.runner_health_update_response import RunnerHealthUpdateResponse
from jobmanager_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://localhost
# See configuration.py for a list of all supported configuration parameters.
configuration = jobmanager_client.Configuration(
    host = "http://localhost"
)


# Enter a context with an instance of the API client
with jobmanager_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = jobmanager_client.RunnersApi(api_client)
    runner_id = 56 # int | 

    try:
        # Update Runner Health
        api_response = api_instance.update_runner_health_v1_runners_runner_id_health_put(runner_id)
        print("The response of RunnersApi->update_runner_health_v1_runners_runner_id_health_put:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling RunnersApi->update_runner_health_v1_runners_runner_id_health_put: %s\n" % e)
```



### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **runner_id** | **int**|  | 

### Return type

[**RunnerHealthUpdateResponse**](RunnerHealthUpdateResponse.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Successful Response |  -  |
**422** | Validation Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)


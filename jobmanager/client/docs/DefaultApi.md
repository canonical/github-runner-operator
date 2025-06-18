# jobmanager_client.DefaultApi

All URIs are relative to *http://localhost*

Method | HTTP request | Description
------------- | ------------- | -------------
[**health_check_health_get**](DefaultApi.md#health_check_health_get) | **GET** /health | Health Check
[**root_get**](DefaultApi.md#root_get) | **GET** / | Root


# **health_check_health_get**
> object health_check_health_get()

Health Check

Health check endpoint for monitoring service status.

This endpoint can be used by monitoring tools and load balancers to
verify the service is operational.

Returns:
    dict: Contains status indicating service health

### Example

```python
import time
import os
import jobmanager_client
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
    api_instance = jobmanager_client.DefaultApi(api_client)

    try:
        # Health Check
        api_response = api_instance.health_check_health_get()
        print("The response of DefaultApi->health_check_health_get:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling DefaultApi->health_check_health_get: %s\n" % e)
```



### Parameters
This endpoint does not need any parameter.

### Return type

**object**

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Successful Response |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **root_get**
> object root_get()

Root

Root endpoint providing basic API information.

Returns:
    dict: Basic API information including:
        - message: API identification
        - version: Current API version
        - status: Running status

### Example

```python
import time
import os
import jobmanager_client
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
    api_instance = jobmanager_client.DefaultApi(api_client)

    try:
        # Root
        api_response = api_instance.root_get()
        print("The response of DefaultApi->root_get:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling DefaultApi->root_get: %s\n" % e)
```



### Parameters
This endpoint does not need any parameter.

### Return type

**object**

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Successful Response |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)


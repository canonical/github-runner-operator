# jobmanager_client.DefaultApi

All URIs are relative to *http://job-manager.internal*

Method | HTTP request | Description
------------- | ------------- | -------------
[**v1_jobs_get**](DefaultApi.md#v1_jobs_get) | **GET** /v1/jobs | Retrieve jobs
[**v1_jobs_job_id_get**](DefaultApi.md#v1_jobs_job_id_get) | **GET** /v1/jobs/{job_id} | Retrieve job details
[**v1_jobs_job_id_health_get**](DefaultApi.md#v1_jobs_job_id_health_get) | **GET** /v1/jobs/{job_id}/health | Retrieve builder status
[**v1_jobs_job_id_health_put**](DefaultApi.md#v1_jobs_job_id_health_put) | **PUT** /v1/jobs/{job_id}/health | Send builder health checks
[**v1_jobs_job_id_put**](DefaultApi.md#v1_jobs_job_id_put) | **PUT** /v1/jobs/{job_id} | Modify a job
[**v1_jobs_job_id_token_post**](DefaultApi.md#v1_jobs_job_id_token_post) | **POST** /v1/jobs/{job_id}/token | Generate a JWT token
[**v1_jobs_post**](DefaultApi.md#v1_jobs_post) | **POST** /v1/jobs | Create a new job


# **v1_jobs_get**
> List[Job] v1_jobs_get(status=status, architecture=architecture, base_series=base_series)

Retrieve jobs



### Example

```python
import time
import os
import jobmanager_client
from jobmanager_client.models.job import Job
from jobmanager_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://job-manager.internal
# See configuration.py for a list of all supported configuration parameters.
configuration = jobmanager_client.Configuration(
    host = "http://job-manager.internal"
)


# Enter a context with an instance of the API client
with jobmanager_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = jobmanager_client.DefaultApi(api_client)
    status = 'status_example' # str |  (optional)
    architecture = 'architecture_example' # str |  (optional)
    base_series = 'base_series_example' # str |  (optional)

    try:
        # Retrieve jobs
        api_response = api_instance.v1_jobs_get(status=status, architecture=architecture, base_series=base_series)
        print("The response of DefaultApi->v1_jobs_get:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling DefaultApi->v1_jobs_get: %s\n" % e)
```



### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **status** | **str**|  | [optional] 
 **architecture** | **str**|  | [optional] 
 **base_series** | **str**|  | [optional] 

### Return type

[**List[Job]**](Job.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | A list of jobs |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **v1_jobs_job_id_get**
> Job v1_jobs_job_id_get(job_id)

Retrieve job details



### Example

```python
import time
import os
import jobmanager_client
from jobmanager_client.models.job import Job
from jobmanager_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://job-manager.internal
# See configuration.py for a list of all supported configuration parameters.
configuration = jobmanager_client.Configuration(
    host = "http://job-manager.internal"
)


# Enter a context with an instance of the API client
with jobmanager_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = jobmanager_client.DefaultApi(api_client)
    job_id = 56 # int | 

    try:
        # Retrieve job details
        api_response = api_instance.v1_jobs_job_id_get(job_id)
        print("The response of DefaultApi->v1_jobs_job_id_get:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling DefaultApi->v1_jobs_job_id_get: %s\n" % e)
```



### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **job_id** | **int**|  | 

### Return type

[**Job**](Job.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Job details returned |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **v1_jobs_job_id_health_get**
> V1JobsJobIdHealthGet200Response v1_jobs_job_id_health_get(job_id)

Retrieve builder status



### Example

```python
import time
import os
import jobmanager_client
from jobmanager_client.models.v1_jobs_job_id_health_get200_response import V1JobsJobIdHealthGet200Response
from jobmanager_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://job-manager.internal
# See configuration.py for a list of all supported configuration parameters.
configuration = jobmanager_client.Configuration(
    host = "http://job-manager.internal"
)


# Enter a context with an instance of the API client
with jobmanager_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = jobmanager_client.DefaultApi(api_client)
    job_id = 56 # int | 

    try:
        # Retrieve builder status
        api_response = api_instance.v1_jobs_job_id_health_get(job_id)
        print("The response of DefaultApi->v1_jobs_job_id_health_get:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling DefaultApi->v1_jobs_job_id_health_get: %s\n" % e)
```



### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **job_id** | **int**|  | 

### Return type

[**V1JobsJobIdHealthGet200Response**](V1JobsJobIdHealthGet200Response.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: Not defined
 - **Accept**: application/json

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Builder status returned |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **v1_jobs_job_id_health_put**
> v1_jobs_job_id_health_put(job_id, v1_jobs_job_id_health_put_request)

Send builder health checks



### Example

```python
import time
import os
import jobmanager_client
from jobmanager_client.models.v1_jobs_job_id_health_put_request import V1JobsJobIdHealthPutRequest
from jobmanager_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://job-manager.internal
# See configuration.py for a list of all supported configuration parameters.
configuration = jobmanager_client.Configuration(
    host = "http://job-manager.internal"
)


# Enter a context with an instance of the API client
with jobmanager_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = jobmanager_client.DefaultApi(api_client)
    job_id = 56 # int | 
    v1_jobs_job_id_health_put_request = jobmanager_client.V1JobsJobIdHealthPutRequest() # V1JobsJobIdHealthPutRequest | 

    try:
        # Send builder health checks
        api_instance.v1_jobs_job_id_health_put(job_id, v1_jobs_job_id_health_put_request)
    except Exception as e:
        print("Exception when calling DefaultApi->v1_jobs_job_id_health_put: %s\n" % e)
```



### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **job_id** | **int**|  | 
 **v1_jobs_job_id_health_put_request** | [**V1JobsJobIdHealthPutRequest**](V1JobsJobIdHealthPutRequest.md)|  | 

### Return type

void (empty response body)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: Not defined

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Health check received |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **v1_jobs_job_id_put**
> Job v1_jobs_job_id_put(job_id, v1_jobs_job_id_put_request)

Modify a job



### Example

```python
import time
import os
import jobmanager_client
from jobmanager_client.models.job import Job
from jobmanager_client.models.v1_jobs_job_id_put_request import V1JobsJobIdPutRequest
from jobmanager_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://job-manager.internal
# See configuration.py for a list of all supported configuration parameters.
configuration = jobmanager_client.Configuration(
    host = "http://job-manager.internal"
)


# Enter a context with an instance of the API client
with jobmanager_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = jobmanager_client.DefaultApi(api_client)
    job_id = 56 # int | 
    v1_jobs_job_id_put_request = jobmanager_client.V1JobsJobIdPutRequest() # V1JobsJobIdPutRequest | 

    try:
        # Modify a job
        api_response = api_instance.v1_jobs_job_id_put(job_id, v1_jobs_job_id_put_request)
        print("The response of DefaultApi->v1_jobs_job_id_put:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling DefaultApi->v1_jobs_job_id_put: %s\n" % e)
```



### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **job_id** | **int**|  | 
 **v1_jobs_job_id_put_request** | [**V1JobsJobIdPutRequest**](V1JobsJobIdPutRequest.md)|  | 

### Return type

[**Job**](Job.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Job modified successfully |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **v1_jobs_job_id_token_post**
> V1JobsJobIdTokenPost200Response v1_jobs_job_id_token_post(job_id, v1_jobs_job_id_token_post_request)

Generate a JWT token



### Example

```python
import time
import os
import jobmanager_client
from jobmanager_client.models.v1_jobs_job_id_token_post200_response import V1JobsJobIdTokenPost200Response
from jobmanager_client.models.v1_jobs_job_id_token_post_request import V1JobsJobIdTokenPostRequest
from jobmanager_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://job-manager.internal
# See configuration.py for a list of all supported configuration parameters.
configuration = jobmanager_client.Configuration(
    host = "http://job-manager.internal"
)


# Enter a context with an instance of the API client
with jobmanager_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = jobmanager_client.DefaultApi(api_client)
    job_id = 56 # int | 
    v1_jobs_job_id_token_post_request = jobmanager_client.V1JobsJobIdTokenPostRequest() # V1JobsJobIdTokenPostRequest | 

    try:
        # Generate a JWT token
        api_response = api_instance.v1_jobs_job_id_token_post(job_id, v1_jobs_job_id_token_post_request)
        print("The response of DefaultApi->v1_jobs_job_id_token_post:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling DefaultApi->v1_jobs_job_id_token_post: %s\n" % e)
```



### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **job_id** | **int**|  | 
 **v1_jobs_job_id_token_post_request** | [**V1JobsJobIdTokenPostRequest**](V1JobsJobIdTokenPostRequest.md)|  | 

### Return type

[**V1JobsJobIdTokenPost200Response**](V1JobsJobIdTokenPost200Response.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**200** | Token generated successfully |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **v1_jobs_post**
> V1JobsPost201Response v1_jobs_post(v1_jobs_post_request)

Create a new job



### Example

```python
import time
import os
import jobmanager_client
from jobmanager_client.models.v1_jobs_post201_response import V1JobsPost201Response
from jobmanager_client.models.v1_jobs_post_request import V1JobsPostRequest
from jobmanager_client.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to http://job-manager.internal
# See configuration.py for a list of all supported configuration parameters.
configuration = jobmanager_client.Configuration(
    host = "http://job-manager.internal"
)


# Enter a context with an instance of the API client
with jobmanager_client.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = jobmanager_client.DefaultApi(api_client)
    v1_jobs_post_request = jobmanager_client.V1JobsPostRequest() # V1JobsPostRequest | 

    try:
        # Create a new job
        api_response = api_instance.v1_jobs_post(v1_jobs_post_request)
        print("The response of DefaultApi->v1_jobs_post:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling DefaultApi->v1_jobs_post: %s\n" % e)
```



### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **v1_jobs_post_request** | [**V1JobsPostRequest**](V1JobsPostRequest.md)|  | 

### Return type

[**V1JobsPost201Response**](V1JobsPost201Response.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**201** | Job created successfully |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)


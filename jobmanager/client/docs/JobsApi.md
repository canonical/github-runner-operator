# jobmanager_client.JobsApi

All URIs are relative to *http://localhost*

Method | HTTP request | Description
------------- | ------------- | -------------
[**create_job_v1_jobs_post**](JobsApi.md#create_job_v1_jobs_post) | **POST** /v1/jobs | Create Job
[**download_object_v1_jobs_job_id_object_object_name_get**](JobsApi.md#download_object_v1_jobs_job_id_object_object_name_get) | **GET** /v1/jobs/{job_id}/object/{object_name} | Download Object
[**generate_token_v1_jobs_job_id_token_post**](JobsApi.md#generate_token_v1_jobs_job_id_token_post) | **POST** /v1/jobs/{job_id}/token | Generate Token
[**get_health_v1_jobs_job_id_health_get**](JobsApi.md#get_health_v1_jobs_job_id_health_get) | **GET** /v1/jobs/{job_id}/health | Get Health
[**get_job_v1_jobs_job_id_get**](JobsApi.md#get_job_v1_jobs_job_id_get) | **GET** /v1/jobs/{job_id} | Get Job
[**get_jobs_v1_jobs_get**](JobsApi.md#get_jobs_v1_jobs_get) | **GET** /v1/jobs | Get Jobs
[**update_health_v1_jobs_job_id_health_put**](JobsApi.md#update_health_v1_jobs_job_id_health_put) | **PUT** /v1/jobs/{job_id}/health | Update Health
[**update_job_v1_jobs_job_id_put**](JobsApi.md#update_job_v1_jobs_job_id_put) | **PUT** /v1/jobs/{job_id} | Update Job


# **create_job_v1_jobs_post**
> JobRead create_job_v1_jobs_post(job_create)

Create Job

Create a new job in the system.

Args:
    job_in: Job creation model containing all required job parameters
    db: Database session dependency
    token: API access token for authorization

Returns:
    JobRead: The created job object

Raises:
    HTTPException 502: If webhook notification fails

### Example

```python
import time
import os
import jobmanager_client
from jobmanager_client.models.job_create import JobCreate
from jobmanager_client.models.job_read import JobRead
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
    api_instance = jobmanager_client.JobsApi(api_client)
    job_create = jobmanager_client.JobCreate() # JobCreate | 

    try:
        # Create Job
        api_response = api_instance.create_job_v1_jobs_post(job_create)
        print("The response of JobsApi->create_job_v1_jobs_post:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling JobsApi->create_job_v1_jobs_post: %s\n" % e)
```



### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **job_create** | [**JobCreate**](JobCreate.md)|  | 

### Return type

[**JobRead**](JobRead.md)

### Authorization

No authorization required

### HTTP request headers

 - **Content-Type**: application/json
 - **Accept**: application/json

### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
**201** | Successful Response |  -  |
**422** | Validation Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **download_object_v1_jobs_job_id_object_object_name_get**
> object download_object_v1_jobs_job_id_object_object_name_get(job_id, object_name)

Download Object

Download an artifact or object associated with a job.

Args:
    job_id: Unique identifier of the job
    object_name: Name of the object/artifact to download
    db: Database session dependency

Returns:
    StreamingResponse: Stream of the requested object data with appropriate
        headers

Raises:
    HTTPException 404: If job is not found

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
    api_instance = jobmanager_client.JobsApi(api_client)
    job_id = 56 # int | 
    object_name = 'object_name_example' # str | 

    try:
        # Download Object
        api_response = api_instance.download_object_v1_jobs_job_id_object_object_name_get(job_id, object_name)
        print("The response of JobsApi->download_object_v1_jobs_job_id_object_object_name_get:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling JobsApi->download_object_v1_jobs_job_id_object_object_name_get: %s\n" % e)
```



### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **job_id** | **int**|  | 
 **object_name** | **str**|  | 

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
**422** | Validation Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **generate_token_v1_jobs_job_id_token_post**
> object generate_token_v1_jobs_job_id_token_post(job_id)

Generate Token

Generate a JWT token for job authentication and set up SSH keys.

Args:
    job_id: Unique identifier of the job
    request: FastAPI request object potentially containing SSH keys
    db: Database session dependency
    token: API access token for authorization

Returns:
    dict: Contains the generated JWT token

Raises:
    HTTPException 404: If job is not found
    HTTPException 500: If SSH key generation fails

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
    api_instance = jobmanager_client.JobsApi(api_client)
    job_id = 56 # int | 

    try:
        # Generate Token
        api_response = api_instance.generate_token_v1_jobs_job_id_token_post(job_id)
        print("The response of JobsApi->generate_token_v1_jobs_job_id_token_post:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling JobsApi->generate_token_v1_jobs_job_id_token_post: %s\n" % e)
```



### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **job_id** | **int**|  | 

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
**422** | Validation Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_health_v1_jobs_job_id_health_get**
> object get_health_v1_jobs_job_id_health_get(job_id)

Get Health

Retrieve the current health status of a job.

Args:
    job_id: Unique identifier of the job
    db: Database session dependency

Returns:
    dict: Health status information including CPU, RAM, disk usage, and job
        status

Raises:
    HTTPException 404: If job is not found

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
    api_instance = jobmanager_client.JobsApi(api_client)
    job_id = 56 # int | 

    try:
        # Get Health
        api_response = api_instance.get_health_v1_jobs_job_id_health_get(job_id)
        print("The response of JobsApi->get_health_v1_jobs_job_id_health_get:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling JobsApi->get_health_v1_jobs_job_id_health_get: %s\n" % e)
```



### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **job_id** | **int**|  | 

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
**422** | Validation Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **get_job_v1_jobs_job_id_get**
> JobRead get_job_v1_jobs_job_id_get(job_id)

Get Job

Retrieve a specific job by its ID.

Args:
    job_id: Unique identifier of the job
    db: Database session dependency

Returns:
    JobRead: The requested job object

Raises:
    HTTPException 404: If job is not found

### Example

```python
import time
import os
import jobmanager_client
from jobmanager_client.models.job_read import JobRead
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
    api_instance = jobmanager_client.JobsApi(api_client)
    job_id = 56 # int | 

    try:
        # Get Job
        api_response = api_instance.get_job_v1_jobs_job_id_get(job_id)
        print("The response of JobsApi->get_job_v1_jobs_job_id_get:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling JobsApi->get_job_v1_jobs_job_id_get: %s\n" % e)
```



### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **job_id** | **int**|  | 

### Return type

[**JobRead**](JobRead.md)

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

# **get_jobs_v1_jobs_get**
> List[JobRead] get_jobs_v1_jobs_get()

Get Jobs

Retrieve a list of all jobs in the system.

Args:
    db: Database session dependency
    token: API access token for authorization

Returns:
    List[JobRead]: List of all jobs

### Example

```python
import time
import os
import jobmanager_client
from jobmanager_client.models.job_read import JobRead
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
    api_instance = jobmanager_client.JobsApi(api_client)

    try:
        # Get Jobs
        api_response = api_instance.get_jobs_v1_jobs_get()
        print("The response of JobsApi->get_jobs_v1_jobs_get:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling JobsApi->get_jobs_v1_jobs_get: %s\n" % e)
```



### Parameters
This endpoint does not need any parameter.

### Return type

[**List[JobRead]**](JobRead.md)

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

# **update_health_v1_jobs_job_id_health_put**
> object update_health_v1_jobs_job_id_health_put(job_id)

Update Health

Update the health status of a running job.

Args:
    job_id: Unique identifier of the job
    db: Database session dependency
    token: Builder token for authorization
    request: FastAPI request object containing health data

Returns:
    dict: The updated health status data

Raises:
    HTTPException 404: If job is not found

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
    api_instance = jobmanager_client.JobsApi(api_client)
    job_id = 56 # int | 

    try:
        # Update Health
        api_response = api_instance.update_health_v1_jobs_job_id_health_put(job_id)
        print("The response of JobsApi->update_health_v1_jobs_job_id_health_put:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling JobsApi->update_health_v1_jobs_job_id_health_put: %s\n" % e)
```



### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **job_id** | **int**|  | 

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
**422** | Validation Error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#documentation-for-api-endpoints) [[Back to Model list]](../README.md#documentation-for-models) [[Back to README]](../README.md)

# **update_job_v1_jobs_job_id_put**
> JobRead update_job_v1_jobs_job_id_put(job_id, job_update)

Update Job

Update an existing job's information.

Args:
    job_id: Unique identifier of the job to update
    job_in: Job update model containing fields to update
    db: Database session dependency
    token: API access token for authorization

Returns:
    JobRead: The updated job object

Raises:
    HTTPException 404: If job is not found

### Example

```python
import time
import os
import jobmanager_client
from jobmanager_client.models.job_read import JobRead
from jobmanager_client.models.job_update import JobUpdate
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
    api_instance = jobmanager_client.JobsApi(api_client)
    job_id = 56 # int | 
    job_update = jobmanager_client.JobUpdate() # JobUpdate | 

    try:
        # Update Job
        api_response = api_instance.update_job_v1_jobs_job_id_put(job_id, job_update)
        print("The response of JobsApi->update_job_v1_jobs_job_id_put:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling JobsApi->update_job_v1_jobs_job_id_put: %s\n" % e)
```



### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **job_id** | **int**|  | 
 **job_update** | [**JobUpdate**](JobUpdate.md)|  | 

### Return type

[**JobRead**](JobRead.md)

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


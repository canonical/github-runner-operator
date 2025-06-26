# jobmanager_client.TokensApi

All URIs are relative to *http://localhost*

Method | HTTP request | Description
------------- | ------------- | -------------
[**create_api_access_token_v1_api_access_token_post**](TokensApi.md#create_api_access_token_v1_api_access_token_post) | **POST** /v1/api_access_token | Create Api Access Token
[**revoke_api_access_token_v1_api_access_token_delete**](TokensApi.md#revoke_api_access_token_v1_api_access_token_delete) | **DELETE** /v1/api_access_token | Revoke Api Access Token


# **create_api_access_token_v1_api_access_token_post**
> object create_api_access_token_v1_api_access_token_post()

Create Api Access Token

Create a new API access token for service authentication.

Args:
    request: FastAPI request object with identity and optional expiration
    db: Database session dependency
    _: Internal-only access check dependency

Returns:
    JSONResponse: Contains the generated token and identity

Raises:
    HTTPException 400: If identity is missing from request
    HTTPException 403: If request is not from internal network

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
    api_instance = jobmanager_client.TokensApi(api_client)

    try:
        # Create Api Access Token
        api_response = api_instance.create_api_access_token_v1_api_access_token_post()
        print("The response of TokensApi->create_api_access_token_v1_api_access_token_post:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling TokensApi->create_api_access_token_v1_api_access_token_post: %s\n" % e)
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

# **revoke_api_access_token_v1_api_access_token_delete**
> object revoke_api_access_token_v1_api_access_token_delete(identity, token)

Revoke Api Access Token

Revoke an existing API access token.

Args:
    identity: Service identity associated with the token
    token: The token value to revoke
    db: Database session dependency
    _: Internal-only access check dependency

Returns:
    dict: Contains the revoked token and identity

Raises:
    HTTPException 403: If request is not from internal network
    HTTPException 404: If token is not found

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
    api_instance = jobmanager_client.TokensApi(api_client)
    identity = 'identity_example' # str | 
    token = 'token_example' # str | 

    try:
        # Revoke Api Access Token
        api_response = api_instance.revoke_api_access_token_v1_api_access_token_delete(identity, token)
        print("The response of TokensApi->revoke_api_access_token_v1_api_access_token_delete:\n")
        pprint(api_response)
    except Exception as e:
        print("Exception when calling TokensApi->revoke_api_access_token_v1_api_access_token_delete: %s\n" % e)
```



### Parameters

Name | Type | Description  | Notes
------------- | ------------- | ------------- | -------------
 **identity** | **str**|  | 
 **token** | **str**|  | 

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


<!-- markdownlint-disable -->

<a href="../../github-runner-manager/src/github_runner_manager/openstack_cloud/openstack_cloud.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `openstack_cloud.openstack_cloud`
Class for accessing OpenStack API for managing servers. 

**Global Variables**
---------------
- **CREATE_SERVER_TIMEOUT**


---

<a href="../../github-runner-manager/src/github_runner_manager/openstack_cloud/openstack_cloud.py#L38"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `OpenStackCredentials`
OpenStack credentials. 



**Attributes:**
 
 - <b>`auth_url`</b>:  The auth url of the OpenStack host. 
 - <b>`project_name`</b>:  The project name to log in to. 
 - <b>`username`</b>:  The username to login with. 
 - <b>`password`</b>:  The password to login with. 
 - <b>`region_name`</b>:  The region. 
 - <b>`user_domain_name`</b>:  The domain name containing the user. 
 - <b>`project_domain_name`</b>:  The domain name containing the project. 

<a href="../../<string>"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(
    auth_url: str,
    project_name: str,
    username: str,
    password: str,
    region_name: str,
    user_domain_name: str,
    project_domain_name: str
) → None
```









---

<a href="../../github-runner-manager/src/github_runner_manager/openstack_cloud/openstack_cloud.py#L61"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `OpenstackInstance`
Represents an OpenStack instance. 



**Attributes:**
 
 - <b>`addresses`</b>:  IP addresses assigned to the server. 
 - <b>`created_at`</b>:  The timestamp in which the instance was created at. 
 - <b>`instance_id`</b>:  ID used by OpenstackCloud class to manage the instances. See docs on the  OpenstackCloud. 
 - <b>`server_id`</b>:  ID of server assigned by OpenStack. 
 - <b>`server_name`</b>:  Name of the server on OpenStack. 
 - <b>`status`</b>:  Status of the server. 

<a href="../../github-runner-manager/src/github_runner_manager/openstack_cloud/openstack_cloud.py#L82"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(server: Server, prefix: str)
```

Construct the object. 



**Args:**
 
 - <b>`server`</b>:  The OpenStack server. 
 - <b>`prefix`</b>:  The name prefix for the servers. 



**Raises:**
 
 - <b>`ValueError`</b>:  Provided server should not be managed under this prefix. 





---

<a href="../../github-runner-manager/src/github_runner_manager/openstack_cloud/openstack_cloud.py#L176"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `OpenstackCloud`
Client to interact with OpenStack cloud. 

The OpenStack server name is managed by this cloud. Caller refers to the instances via instance_id. If the caller needs the server name, e.g., for logging, it can be queried with get_server_name. 

<a href="../../github-runner-manager/src/github_runner_manager/openstack_cloud/openstack_cloud.py#L184"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(credentials: OpenStackCredentials, prefix: str, system_user: str)
```

Create the object. 



**Args:**
 
 - <b>`credentials`</b>:  The OpenStack authorization information. 
 - <b>`prefix`</b>:  Prefix attached to names of resource managed by this instance. Used for  identifying which resource belongs to this instance. 
 - <b>`system_user`</b>:  The system user to own the key files. 




---

<a href="../../github-runner-manager/src/github_runner_manager/openstack_cloud/openstack_cloud.py#L383"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `cleanup`

```python
cleanup() → None
```

Cleanup unused key files and openstack keypairs. 

---

<a href="../../github-runner-manager/src/github_runner_manager/openstack_cloud/openstack_cloud.py#L273"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `delete_instance`

```python
delete_instance(instance_id: str) → None
```

Delete a openstack instance. 



**Args:**
 
 - <b>`instance_id`</b>:  The instance ID of the instance to delete. 

---

<a href="../../github-runner-manager/src/github_runner_manager/openstack_cloud/openstack_cloud.py#L254"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_instance`

```python
get_instance(instance_id: str) → OpenstackInstance | None
```

Get OpenStack instance by instance ID. 



**Args:**
 
 - <b>`instance_id`</b>:  The instance ID. 



**Returns:**
 The OpenStack instance if found. 

---

<a href="../../github-runner-manager/src/github_runner_manager/openstack_cloud/openstack_cloud.py#L361"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_instances`

```python
get_instances() → tuple[OpenstackInstance, ]
```

Get all OpenStack instances. 



**Returns:**
  The OpenStack instances. 

---

<a href="../../github-runner-manager/src/github_runner_manager/openstack_cloud/openstack_cloud.py#L392"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_server_name`

```python
get_server_name(instance_id: str) → str
```

Get server name on OpenStack. 



**Args:**
 
 - <b>`instance_id`</b>:  ID used to identify a instance. 



**Returns:**
 The OpenStack server name. 

---

<a href="../../github-runner-manager/src/github_runner_manager/openstack_cloud/openstack_cloud.py#L307"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_ssh_connection`

```python
get_ssh_connection(instance: OpenstackInstance) → Connection
```

Get SSH connection to an OpenStack instance. 



**Args:**
 
 - <b>`instance`</b>:  The OpenStack instance to connect to. 



**Raises:**
 
 - <b>`SSHError`</b>:  Unable to get a working SSH connection to the instance. 
 - <b>`KeyfileError`</b>:  Unable to find the keyfile to connect to the instance. 



**Returns:**
 SSH connection object. 

---

<a href="../../github-runner-manager/src/github_runner_manager/openstack_cloud/openstack_cloud.py#L198"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `launch_instance`

```python
launch_instance(
    instance_id: str,
    image: str,
    flavor: str,
    network: str,
    cloud_init: str
) → OpenstackInstance
```

Create an OpenStack instance. 



**Args:**
 
 - <b>`instance_id`</b>:  The instance ID to form the instance name. 
 - <b>`image`</b>:  The image used to create the instance. 
 - <b>`flavor`</b>:  The flavor used to create the instance. 
 - <b>`network`</b>:  The network used to create the instance. 
 - <b>`cloud_init`</b>:  The cloud init userdata to startup the instance. 



**Raises:**
 
 - <b>`OpenStackError`</b>:  Unable to create OpenStack server. 



**Returns:**
 The OpenStack instance created. 



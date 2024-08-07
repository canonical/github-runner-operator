<!-- markdownlint-disable -->

<a href="../src/openstack_cloud/openstack_cloud.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `openstack_cloud.openstack_cloud`
Class for accessing OpenStack API for managing servers. 



---

<a href="../src/openstack_cloud/openstack_cloud.py#L40"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `OpenstackInstance`
Represents an OpenStack instance. 



**Attributes:**
 
 - <b>`server_id`</b>:  ID of server assigned by OpenStack. 
 - <b>`server_name`</b>:  Name of the server on OpenStack. 
 - <b>`instance_id`</b>:  ID used by OpenstackCloud class to manage the instances. See docs on the  OpenstackCloud. 
 - <b>`addresses`</b>:  IP addresses assigned to the server. 
 - <b>`status`</b>:  Status of the server. 

<a href="../src/openstack_cloud/openstack_cloud.py#L59"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(server: Server, prefix: str)
```

Construct the object. 



**Args:**
 
 - <b>`server`</b>:  The OpenStack server. 
 - <b>`prefix`</b>:  The name prefix for the servers. 





---

<a href="../src/openstack_cloud/openstack_cloud.py#L117"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `OpenstackCloud`
Client to interact with OpenStack cloud. 

The OpenStack server name is managed by this cloud. Caller refers to the instances via instance_id. If the caller needs the server name, e.g., for logging, it can be queried with get_server_name. 

<a href="../src/openstack_cloud/openstack_cloud.py#L125"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(clouds_config: dict[str, dict], cloud: str, prefix: str)
```

Create the object. 



**Args:**
 
 - <b>`clouds_config`</b>:  The openstack clouds.yaml in dict format. 
 - <b>`cloud`</b>:  The name of cloud to use in the clouds.yaml. 
 - <b>`prefix`</b>:  Prefix attached to names of resource managed by this instance. Used for  identifying which resource belongs to this instance. 




---

<a href="../src/openstack_cloud/openstack_cloud.py#L313"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `cleanup`

```python
cleanup() → None
```

Cleanup unused openstack resources. 

---

<a href="../src/openstack_cloud/openstack_cloud.py#L219"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `delete_instance`

```python
delete_instance(instance_id: str) → None
```

Delete a openstack instance. 



**Args:**
 
 - <b>`instance_id`</b>:  The instance ID of the instance to delete. 

---

<a href="../src/openstack_cloud/openstack_cloud.py#L200"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_instance`

```python
get_instance(instance_id: str) → OpenstackInstance
```

Get OpenStack instance by instance ID. 



**Args:**
 
 - <b>`instance_id`</b>:  The instance ID. 



**Returns:**
 The OpenStack instance. 

---

<a href="../src/openstack_cloud/openstack_cloud.py#L290"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_instances`

```python
get_instances() → tuple[OpenstackInstance]
```

Get all OpenStack instances. 



**Returns:**
  The OpenStack instances. 

---

<a href="../src/openstack_cloud/openstack_cloud.py#L323"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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

<a href="../src/openstack_cloud/openstack_cloud.py#L241"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_ssh_connection`

```python
get_ssh_connection(instance: OpenstackInstance) → Connection
```

Get SSH connection to an OpenStack instance. 



**Args:**
 
 - <b>`instance`</b>:  The OpenStack instance to connect to. 



**Returns:**
 SSH connection object. 

---

<a href="../src/openstack_cloud/openstack_cloud.py#L138"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `launch_instance`

```python
launch_instance(
    instance_id: str,
    image: str,
    flavor: str,
    network: str,
    userdata: str
) → OpenstackInstance
```

Create an OpenStack instance. 



**Args:**
 
 - <b>`instance_id`</b>:  The instance ID to form the instance name. 
 - <b>`image`</b>:  The image used to create the instance. 
 - <b>`flavor`</b>:  The flavor used to create the instance. 
 - <b>`network`</b>:  The network used to create the instance. 
 - <b>`userdata`</b>:  The cloud init userdata to startup the instance. 



**Returns:**
 The OpenStack instance created. 



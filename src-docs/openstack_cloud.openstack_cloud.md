<!-- markdownlint-disable -->

<a href="../src/openstack_cloud/openstack_cloud.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `openstack_cloud.openstack_cloud`






---

<a href="../src/openstack_cloud/openstack_cloud.py#L39"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `OpenstackInstance`
OpenstackInstance(server: openstack.compute.v2.server.Server, prefix: str) 

<a href="../src/openstack_cloud/openstack_cloud.py#L47"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(server: Server, prefix: str)
```









---

<a href="../src/openstack_cloud/openstack_cloud.py#L99"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `OpenstackCloud`




<a href="../src/openstack_cloud/openstack_cloud.py#L101"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(clouds_config: dict[str, dict], cloud: str, prefix: str)
```

Create a OpenstackCloud instance. 



**Args:**
 
 - <b>`clouds_config`</b>:  The openstack clouds.yaml in dict format. 
 - <b>`cloud`</b>:  The name of cloud to use in the clouds.yaml. 
 - <b>`prefix`</b>:  Prefix attached to names of resource managed by this instance. Used for  identifying which resource belongs to this instance. 




---

<a href="../src/openstack_cloud/openstack_cloud.py#L244"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `cleanup`

```python
cleanup() → None
```





---

<a href="../src/openstack_cloud/openstack_cloud.py#L173"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `delete_instance`

```python
delete_instance(instance_id: str) → None
```





---

<a href="../src/openstack_cloud/openstack_cloud.py#L164"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_instance`

```python
get_instance(instance_id: str) → OpenstackInstance
```





---

<a href="../src/openstack_cloud/openstack_cloud.py#L318"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_instance_name`

```python
get_instance_name(name: str) → str
```





---

<a href="../src/openstack_cloud/openstack_cloud.py#L231"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_instances`

```python
get_instances() → tuple[OpenstackInstance]
```





---

<a href="../src/openstack_cloud/openstack_cloud.py#L190"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_ssh_connection`

```python
get_ssh_connection(instance: OpenstackInstance) → Connection
```





---

<a href="../src/openstack_cloud/openstack_cloud.py#L114"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

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







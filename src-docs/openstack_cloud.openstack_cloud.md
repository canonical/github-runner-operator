<!-- markdownlint-disable -->

<a href="../src/openstack_cloud/openstack_cloud.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `openstack_cloud.openstack_cloud`






---

<a href="../src/openstack_cloud/openstack_cloud.py#L37"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `OpenstackInstance`
OpenstackInstance(server: openstack.compute.v2.server.Server) 

<a href="../src/openstack_cloud/openstack_cloud.py#L43"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(server: Server)
```









---

<a href="../src/openstack_cloud/openstack_cloud.py#L86"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `OpenstackCloud`




<a href="../src/openstack_cloud/openstack_cloud.py#L88"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(cloud_config: dict[str, dict], prefix: str)
```

Create a OpenstackCloud instance. 



**Args:**
 
 - <b>`cloud_config`</b>:  The openstack clouds.yaml in dict format. The first cloud in the yaml is   used. prefix: 




---

<a href="../src/openstack_cloud/openstack_cloud.py#L121"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `delete_instance`

```python
delete_instance(name: str)
```





---

<a href="../src/openstack_cloud/openstack_cloud.py#L167"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_instances`

```python
get_instances(name: str) → list[OpenstackInstance]
```





---

<a href="../src/openstack_cloud/openstack_cloud.py#L130"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `get_ssh_connection`

```python
get_ssh_connection(instance: OpenstackInstance) → Connection
```





---

<a href="../src/openstack_cloud/openstack_cloud.py#L99"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `launch_instance`

```python
launch_instance(
    name: str,
    image: str,
    flavor: str,
    network: str,
    userdata: str
) → OpenstackInstance
```







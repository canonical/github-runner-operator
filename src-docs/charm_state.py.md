<!-- markdownlint-disable -->

<a href="../src/charm_state.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `charm_state.py`
State of the Charm. 

**Global Variables**
---------------
- **REACTIVE_MODE_NOT_SUPPORTED_WITH_LXD_ERR_MSG**
- **ARCHITECTURES_ARM64**
- **ARCHITECTURES_X86**
- **BASE_IMAGE_CONFIG_NAME**
- **DENYLIST_CONFIG_NAME**
- **DOCKERHUB_MIRROR_CONFIG_NAME**
- **GROUP_CONFIG_NAME**
- **LABELS_CONFIG_NAME**
- **OPENSTACK_CLOUDS_YAML_CONFIG_NAME**
- **OPENSTACK_NETWORK_CONFIG_NAME**
- **OPENSTACK_FLAVOR_CONFIG_NAME**
- **PATH_CONFIG_NAME**
- **RECONCILE_INTERVAL_CONFIG_NAME**
- **REPO_POLICY_COMPLIANCE_TOKEN_CONFIG_NAME**
- **REPO_POLICY_COMPLIANCE_URL_CONFIG_NAME**
- **RUNNER_STORAGE_CONFIG_NAME**
- **SENSITIVE_PLACEHOLDER**
- **TEST_MODE_CONFIG_NAME**
- **TOKEN_CONFIG_NAME**
- **USE_APROXY_CONFIG_NAME**
- **VIRTUAL_MACHINES_CONFIG_NAME**
- **VM_CPU_CONFIG_NAME**
- **VM_MEMORY_CONFIG_NAME**
- **VM_DISK_CONFIG_NAME**
- **COS_AGENT_INTEGRATION_NAME**
- **DEBUG_SSH_INTEGRATION_NAME**
- **IMAGE_INTEGRATION_NAME**
- **MONGO_DB_INTEGRATION_NAME**
- **LTS_IMAGE_VERSION_TAG_MAP**


---

## <kbd>class</kbd> `AnyHttpsUrl`
Represents an HTTPS URL. 



**Attributes:**
 
 - <b>`allowed_schemes`</b>:  Allowed schemes for the URL. 





---

## <kbd>class</kbd> `Arch`
Supported system architectures. 



**Attributes:**
 
 - <b>`ARM64`</b>:  Represents an ARM64 system architecture. 
 - <b>`X64`</b>:  Represents an X64/AMD64 system architecture. 





---

## <kbd>class</kbd> `BaseImage`
The ubuntu OS base image to build and deploy runners on. 



**Attributes:**
 
 - <b>`JAMMY`</b>:  The jammy ubuntu LTS image. 
 - <b>`NOBLE`</b>:  The noble ubuntu LTS image. 





---

## <kbd>class</kbd> `CharmConfig`
General charm configuration. 

Some charm configurations are grouped into other configuration models. 



**Attributes:**
 
 - <b>`denylist`</b>:  List of IPv4 to block the runners from accessing. 
 - <b>`dockerhub_mirror`</b>:  Private docker registry as dockerhub mirror for the runners to use. 
 - <b>`labels`</b>:  Additional runner labels to append to default (i.e. os, flavor, architecture). 
 - <b>`openstack_clouds_yaml`</b>:  The openstack clouds.yaml configuration. 
 - <b>`path`</b>:  GitHub repository path in the format '<owner>/<repo>', or the GitHub organization  name. 
 - <b>`reconcile_interval`</b>:  Time between each reconciliation of runners in minutes. 
 - <b>`repo_policy_compliance`</b>:  Configuration for the repo policy compliance service. 
 - <b>`token`</b>:  GitHub personal access token for GitHub API. 




---

<a href="../src/charm_state.py#L448"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `check_reconcile_interval`

```python
check_reconcile_interval(reconcile_interval: int) → int
```

Validate the general charm configuration. 



**Args:**
 
 - <b>`reconcile_interval`</b>:  The value of reconcile_interval passed to class instantiation. 



**Raises:**
 
 - <b>`ValueError`</b>:  if an invalid reconcile_interval value of less than 2 has been passed. 



**Returns:**
 The validated reconcile_interval value. 

---

<a href="../src/charm_state.py#L476"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(charm: CharmBase) → CharmConfig
```

Initialize the config from charm. 



**Args:**
 
 - <b>`charm`</b>:  The charm instance. 



**Raises:**
 
 - <b>`CharmConfigInvalidError`</b>:  If any invalid configuration has been set on the charm. 



**Returns:**
 Current config of the charm. 


---

## <kbd>class</kbd> `CharmConfigInvalidError`
Raised when charm config is invalid. 



**Attributes:**
 
 - <b>`msg`</b>:  Explanation of the error. 

<a href="../src/charm_state.py#L196"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str)
```

Initialize a new instance of the CharmConfigInvalidError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 





---

## <kbd>class</kbd> `CharmState`
The charm state. 



**Attributes:**
 
 - <b>`arch`</b>:  The underlying compute architecture, i.e. x86_64, amd64, arm64/aarch64. 
 - <b>`charm_config`</b>:  Configuration of the juju charm. 
 - <b>`is_metrics_logging_available`</b>:  Whether the charm is able to issue metrics. 
 - <b>`proxy_config`</b>:  Proxy-related configuration. 
 - <b>`instance_type`</b>:  The type of instances, e.g., local lxd, openstack. 
 - <b>`reactive_config`</b>:  The charm configuration related to reactive spawning mode. 
 - <b>`runner_config`</b>:  The charm configuration related to runner VM configuration. 
 - <b>`ssh_debug_connections`</b>:  SSH debug connections configuration information. 




---

<a href="../src/charm_state.py#L1147"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(charm: CharmBase, database: DatabaseRequires) → CharmState
```

Initialize the state from charm. 



**Args:**
 
 - <b>`charm`</b>:  The charm instance. 
 - <b>`database`</b>:  The database instance. 



**Raises:**
 
 - <b>`CharmConfigInvalidError`</b>:  If an invalid configuration was set. 



**Returns:**
 Current state of the charm. 


---

## <kbd>class</kbd> `GithubConfig`
Charm configuration related to GitHub. 



**Attributes:**
 
 - <b>`token`</b>:  The Github API access token (PAT). 
 - <b>`path`</b>:  The Github org/repo path. 




---

<a href="../src/charm_state.py#L109"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(charm: CharmBase) → GithubConfig
```

Get github related charm configuration values from charm. 



**Args:**
 
 - <b>`charm`</b>:  The charm instance. 



**Raises:**
 
 - <b>`CharmConfigInvalidError`</b>:  If an invalid configuration value was set. 



**Returns:**
 The parsed GitHub configuration values. 


---

## <kbd>class</kbd> `ImmutableConfigChangedError`
Represents an error when changing immutable charm state. 

<a href="../src/charm_state.py#L1015"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str)
```

Initialize a new instance of the ImmutableConfigChangedError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 





---

## <kbd>class</kbd> `InstanceType`
Type of instance for runner. 



**Attributes:**
 
 - <b>`LOCAL_LXD`</b>:  LXD instance on the local juju machine. 
 - <b>`OPENSTACK`</b>:  OpenStack instance on a cloud. 





---

## <kbd>class</kbd> `LocalLxdRunnerConfig`
Runner configurations for local LXD instances. 



**Attributes:**
 
 - <b>`base_image`</b>:  The ubuntu base image to run the runner virtual machines on. 
 - <b>`virtual_machines`</b>:  Number of virtual machine-based runner to spawn. 
 - <b>`virtual_machine_resources`</b>:  Hardware resource used by one virtual machine for a runner. 
 - <b>`runner_storage`</b>:  Storage to be used as disk for the runner. 




---

<a href="../src/charm_state.py#L746"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `check_virtual_machine_resources`

```python
check_virtual_machine_resources(
    vm_resources: VirtualMachineResources
) → VirtualMachineResources
```

Validate the virtual_machine_resources field values. 



**Args:**
 
 - <b>`vm_resources`</b>:  the virtual_machine_resources value to validate. 



**Raises:**
 
 - <b>`ValueError`</b>:  if an invalid number of cpu was given or invalid memory/disk size was  given. 



**Returns:**
 The validated virtual_machine_resources value. 

---

<a href="../src/charm_state.py#L724"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `check_virtual_machines`

```python
check_virtual_machines(virtual_machines: int) → int
```

Validate the virtual machines configuration value. 



**Args:**
 
 - <b>`virtual_machines`</b>:  The virtual machines value to validate. 



**Raises:**
 
 - <b>`ValueError`</b>:  if a negative integer was passed. 



**Returns:**
 Validated virtual_machines value. 

---

<a href="../src/charm_state.py#L672"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(charm: CharmBase) → LocalLxdRunnerConfig
```

Initialize the config from charm. 



**Args:**
 
 - <b>`charm`</b>:  The charm instance. 



**Raises:**
 
 - <b>`CharmConfigInvalidError`</b>:  if an invalid runner charm config has been set on the charm. 



**Returns:**
 Local LXD runner config of the charm. 


---

## <kbd>class</kbd> `OpenStackCloudsYAML`
The OpenStack clouds YAML dict mapping. 



**Attributes:**
 
 - <b>`clouds`</b>:  The map of cloud name to cloud connection info. 





---

## <kbd>class</kbd> `OpenstackImage`
OpenstackImage from image builder relation data. 



**Attributes:**
 
 - <b>`id`</b>:  The OpenStack image ID. 
 - <b>`tags`</b>:  Image tags, e.g. jammy 




---

<a href="../src/charm_state.py#L582"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(charm: CharmBase) → OpenstackImage | None
```

Initialize the OpenstackImage info from relation data. 

None represents relation not established. None values for id/tags represent image not yet ready but the relation exists. 



**Args:**
 
 - <b>`charm`</b>:  The charm instance. 



**Returns:**
 OpenstackImage metadata from charm relation data. 


---

## <kbd>class</kbd> `OpenstackRunnerConfig`
Runner configuration for OpenStack Instances. 



**Attributes:**
 
 - <b>`virtual_machines`</b>:  Number of virtual machine-based runner to spawn. 
 - <b>`openstack_flavor`</b>:  flavor on openstack to use for virtual machines. 
 - <b>`openstack_network`</b>:  Network on openstack to use for virtual machines. 
 - <b>`openstack_image`</b>:  Openstack image to use for virtual machines. 




---

<a href="../src/charm_state.py#L624"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(charm: CharmBase) → OpenstackRunnerConfig
```

Initialize the config from charm. 



**Args:**
 
 - <b>`charm`</b>:  The charm instance. 



**Raises:**
 
 - <b>`CharmConfigInvalidError`</b>:  Error with charm configuration virtual-machines not of int  type. 



**Returns:**
 Openstack runner config of the charm. 


---

## <kbd>class</kbd> `ProxyConfig`
Proxy configuration. 



**Attributes:**
 
 - <b>`aproxy_address`</b>:  The address of aproxy snap instance if use_aproxy is enabled. 
 - <b>`http`</b>:  HTTP proxy address. 
 - <b>`https`</b>:  HTTPS proxy address. 
 - <b>`no_proxy`</b>:  Comma-separated list of hosts that should not be proxied. 
 - <b>`use_aproxy`</b>:  Whether aproxy should be used for the runners. 


---

#### <kbd>property</kbd> aproxy_address

Return the aproxy address. 



---

<a href="../src/charm_state.py#L816"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `check_use_aproxy`

```python
check_use_aproxy(use_aproxy: bool, values: dict) → bool
```

Validate the proxy configuration. 



**Args:**
 
 - <b>`use_aproxy`</b>:  Value of use_aproxy variable. 
 - <b>`values`</b>:  Values in the pydantic model. 



**Raises:**
 
 - <b>`ValueError`</b>:  if use_aproxy was set but no http/https was passed. 



**Returns:**
 Validated use_aproxy value. 

---

<a href="../src/charm_state.py#L844"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(charm: CharmBase) → ProxyConfig
```

Initialize the proxy config from charm. 



**Args:**
 
 - <b>`charm`</b>:  The charm instance. 



**Returns:**
 Current proxy config of the charm. 


---

## <kbd>class</kbd> `ReactiveConfig`
Represents the configuration for reactive scheduling. 



**Attributes:**
 
 - <b>`mq_uri`</b>:  The URI of the MQ to use to spawn runners reactively. 




---

<a href="../src/charm_state.py#L978"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_database`

```python
from_database(database: DatabaseRequires) → ReactiveConfig | None
```

Initialize the ReactiveConfig from charm config and integration data. 



**Args:**
 
 - <b>`database`</b>:  The database to fetch integration data from. 



**Returns:**
 The connection information for the reactive MQ or None if not available. 



**Raises:**
 
 - <b>`MissingMongoDBError`</b>:  If the information on howto access MongoDB  is missing in the integration data. 


---

## <kbd>class</kbd> `RepoPolicyComplianceConfig`
Configuration for the repo policy compliance service. 



**Attributes:**
 
 - <b>`token`</b>:  Token for the repo policy compliance service. 
 - <b>`url`</b>:  URL of the repo policy compliance service. 




---

<a href="../src/charm_state.py#L263"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(charm: CharmBase) → RepoPolicyComplianceConfig
```

Initialize the config from charm. 



**Args:**
 
 - <b>`charm`</b>:  The charm instance. 



**Raises:**
 
 - <b>`CharmConfigInvalidError`</b>:  If an invalid configuration was set. 



**Returns:**
 Current repo-policy-compliance config. 


---

## <kbd>class</kbd> `RunnerStorage`
Supported storage as runner disk. 



**Attributes:**
 
 - <b>`JUJU_STORAGE`</b>:  Represents runner storage from Juju storage. 
 - <b>`MEMORY`</b>:  Represents tempfs storage (ramdisk). 





---

## <kbd>class</kbd> `SSHDebugConnection`
SSH connection information for debug workflow. 



**Attributes:**
 
 - <b>`host`</b>:  The SSH relay server host IP address inside the VPN. 
 - <b>`port`</b>:  The SSH relay server port. 
 - <b>`rsa_fingerprint`</b>:  The host SSH server public RSA key fingerprint. 
 - <b>`ed25519_fingerprint`</b>:  The host SSH server public ed25519 key fingerprint. 




---

<a href="../src/charm_state.py#L930"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `from_charm`

```python
from_charm(charm: CharmBase) → list['SSHDebugConnection']
```

Initialize the SSHDebugInfo from charm relation data. 



**Args:**
 
 - <b>`charm`</b>:  The charm instance. 



**Returns:**
 List of connection information for ssh debug access. 


---

## <kbd>class</kbd> `UnsupportedArchitectureError`
Raised when given machine charm architecture is unsupported. 



**Attributes:**
 
 - <b>`arch`</b>:  The current machine architecture. 

<a href="../src/charm_state.py#L887"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(arch: str) → None
```

Initialize a new instance of the CharmConfigInvalidError exception. 



**Args:**
 
 - <b>`arch`</b>:  The current machine architecture. 





---

## <kbd>class</kbd> `VirtualMachineResources`
Virtual machine resource configuration. 



**Attributes:**
 
 - <b>`cpu`</b>:  Number of vCPU for the virtual machine. 
 - <b>`memory`</b>:  Amount of memory for the virtual machine. 
 - <b>`disk`</b>:  Amount of disk for the virtual machine. 






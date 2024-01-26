<!-- markdownlint-disable -->

<a href="../src/firewall.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `firewall.py`
The runner firewall manager. 



---

## <kbd>class</kbd> `Firewall`
Represent a firewall and provides methods to refresh its configuration. 

<a href="../src/firewall.py#L50"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(network: str)
```

Initialize a new Firewall instance. 



**Args:**
 
 - <b>`network`</b>:  The LXD network name. 




---

<a href="../src/firewall.py#L58"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `get_host_ip`

```python
get_host_ip() → str
```

Get the host IP address for the corresponding LXD network. 



**Returns:**
  The host IP address. 

---

<a href="../src/firewall.py#L83"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `refresh_firewall`

```python
refresh_firewall(
    denylist: List[FirewallEntry],
    allowlist: Optional[List[FirewallEntry]] = None
)
```

Refresh the firewall configuration. 



**Args:**
 
 - <b>`denylist`</b>:  The list of FirewallEntry objects to allow. 


---

## <kbd>class</kbd> `FirewallEntry`
Represent an entry in the firewall. 



**Attributes:**
 
 - <b>`ip_range`</b>:  The IP address range using CIDR notation. 




---

<a href="../src/firewall.py#L25"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>classmethod</kbd> `decode`

```python
decode(entry: str) → FirewallEntry
```

Decode a firewall entry from a string. 



**Args:**
 
 - <b>`entry`</b>:  The firewall entry string, e.g. '192.168.0.1:80' or '192.168.0.0/24:80-90:udp'. 



**Returns:**
 
 - <b>`FirewallEntry`</b>:  A FirewallEntry instance representing the decoded entry. 



**Raises:**
 
 - <b>`ValueError`</b>:  If the entry string is not in the expected format. 



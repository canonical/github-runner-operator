<!-- markdownlint-disable -->

<a href="../src/promtail.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `promtail.py`
Functions for operating Promtail. 

**Global Variables**
---------------
- **PROMTAIL_BASE_URL**
- **SYSTEMCTL_PATH_STR**
- **PROMTAIL_BINARY_FILE_MODE**
- **JINJA2_TEMPLATE_PATH**

---

<a href="../src/promtail.py#L162"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `setup`

```python
setup(config: Config) → None
```

Set up Promtail. 

Installs, configures and starts Promtail. 

If Promtail has not already been installed, it will be installed and configured to send logs to Loki. If Promtail is already running, it will be reconfigured and restarted. 



**Args:**
 
 - <b>`config`</b>:  The configuration for Promtail. 


---

<a href="../src/promtail.py#L189"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `restart`

```python
restart() → None
```

Restart Promtail. 


---

<a href="../src/promtail.py#L194"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `stop`

```python
stop() → None
```

Stop Promtail. 


---

<a href="../src/promtail.py#L199"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `is_running`

```python
is_running() → bool
```

Check if Promtail is running. 



**Returns:**
  True if Promtail is running, False otherwise. 


---

## <kbd>class</kbd> `Config`
Configuration options for Promtail. 

Attrs:  loki_endpoint: The Loki endpoint to send logs to.  proxies: Proxy settings.  promtail_download_info: Information about the Promtail download. 





---

## <kbd>class</kbd> `PromtailDownloadInfo`
Information about the Promtail download. 

Attrs:  url: The URL to download Promtail from.  zip_sha256: The SHA256 hash of the Promtail zip file.  bin_sha256: The SHA256 hash of the Promtail binary. 





---

## <kbd>class</kbd> `PromtailInstallationError`
Represents an error during installation of Promtail. 

<a href="../src/promtail.py#L36"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(msg: str)
```

Initialize a new instance of the PromtailInstallationError exception. 



**Args:**
 
 - <b>`msg`</b>:  Explanation of the error. 






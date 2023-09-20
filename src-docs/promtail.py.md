<!-- markdownlint-disable -->

<a href="../src/promtail.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `promtail.py`
Functions for operating Promtail. 


---

<a href="../src/promtail.py#L21"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `start`

```python
start(config: PromtailConfig) → None
```

Start Promtail. 

If Promtail has not already been installed, it will be installed and configured to send logs to Loki. If Promtail is already running, it will be reconfigured and restarted. 



**Args:**
 
 - <b>`config`</b>:  The configuration for Promtail. 


---

<a href="../src/promtail.py#L33"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `stop`

```python
stop() → None
```

Stop Promtail. 


---

## <kbd>class</kbd> `PromtailConfig`
Configuration options for Promtail. 






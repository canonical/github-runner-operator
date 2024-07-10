<!-- markdownlint-disable -->

<a href="../src/logrotate.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `logrotate`
Logrotate setup and configuration. 

**Global Variables**
---------------
- **LOG_ROTATE_TIMER_SYSTEMD_SERVICE**
- **SYSTEMCTL_PATH**

---

<a href="../src/logrotate.py#L56"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `setup`

```python
setup() → None
```

Set up logrotate. 



**Raises:**
 
 - <b>`LogrotateSetupError`</b>:  If the logrotate.timer cannot be enabled. 


---

<a href="../src/logrotate.py#L94"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>function</kbd> `configure`

```python
configure(logrotate_config: LogrotateConfig) → None
```

Write a particular logrotate config to disk. 



**Args:**
 
 - <b>`logrotate_config`</b>:  The logrotate config. 


---

<a href="../src/logrotate.py#L20"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `LogrotateFrequency`
The frequency of log rotation. 



**Attributes:**
 
 - <b>`DAILY`</b>:  Rotate the log daily. 
 - <b>`WEEKLY`</b>:  Rotate the log weekly. 
 - <b>`MONTHLY`</b>:  Rotate the log monthly. 
 - <b>`YEARLY`</b>:  Rotate the log yearly. 





---

<a href="../src/logrotate.py#L36"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `LogrotateConfig`
Configuration for logrotate. 



**Attributes:**
 
 - <b>`name`</b>:  The name of the logrotate configuration. 
 - <b>`log_path_glob_pattern`</b>:  The glob pattern for the log path. 
 - <b>`rotate`</b>:  The number of log files to keep. 
 - <b>`create`</b>:  Whether to create the log file if it does not exist. 
 - <b>`notifempty`</b>:  Whether to not rotate the log file if it is empty. 
 - <b>`frequency`</b>:  The frequency of log rotation. 






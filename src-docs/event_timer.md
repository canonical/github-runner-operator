<!-- markdownlint-disable -->

<a href="../src/event_timer.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `event_timer`
EventTimer for scheduling dispatch of juju event on regular intervals. 

**Global Variables**
---------------
- **BIN_SYSTEMCTL**


---

<a href="../src/event_timer.py#L19"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `TimerError`
Generic timer error as base exception. 





---

<a href="../src/event_timer.py#L23"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `TimerEnableError`
Raised when unable to enable a event timer. 





---

<a href="../src/event_timer.py#L27"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `TimerDisableError`
Raised when unable to disable a event timer. 





---

<a href="../src/event_timer.py#L31"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `TimerStatusError`
Raised when unable to check status of a event timer. 





---

<a href="../src/event_timer.py#L35"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `EventConfig`
Configuration used by service and timer templates. 



**Attributes:**
 
 - <b>`event`</b>:  Name of the event. 
 - <b>`interval`</b>:  Minutes between the event trigger. 
 - <b>`random_delay`</b>:  Minutes of random delay added between event trigger. 
 - <b>`timeout`</b>:  Minutes before the event handle is timeout. 
 - <b>`unit`</b>:  Name of the juju unit. 





---

<a href="../src/event_timer.py#L53"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

## <kbd>class</kbd> `EventTimer`
Manages the timer to emit juju events at regular intervals. 



**Attributes:**
 
 - <b>`unit_name`</b> (str):  Name of the juju unit to emit events to. 

<a href="../src/event_timer.py#L62"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `__init__`

```python
__init__(unit_name: str)
```

Construct the timer manager. 



**Args:**
 
 - <b>`unit_name`</b>:  Name of the juju unit to emit events to. 




---

<a href="../src/event_timer.py#L151"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `disable_event_timer`

```python
disable_event_timer(event_name: str) → None
```

Disable the systemd timer for the given event. 



**Args:**
 
 - <b>`event_name`</b>:  Name of the juju event to disable. 



**Raises:**
 
 - <b>`TimerDisableError`</b>:  Timer cannot be stopped. Events will be emitted continuously. 

---

<a href="../src/event_timer.py#L110"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `ensure_event_timer`

```python
ensure_event_timer(
    event_name: str,
    interval: int,
    timeout: Optional[int] = None
) → None
```

Ensure that a systemd service and timer are registered to dispatch the given event. 

The interval is how frequently, in minutes, the event should be dispatched. 

The timeout is the number of seconds before an event is timed out. If not set or 0, it defaults to half the interval period. 



**Args:**
 
 - <b>`event_name`</b>:  Name of the juju event to schedule. 
 - <b>`interval`</b>:  Number of minutes between emitting each event. 
 - <b>`timeout`</b>:  Timeout for each event handle in minutes. 



**Raises:**
 
 - <b>`TimerEnableError`</b>:  Timer cannot be started. Events will be not emitted. 

---

<a href="../src/event_timer.py#L87"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>method</kbd> `is_active`

```python
is_active(event_name: str) → bool
```

Check if the systemd timer is active for the given event. 



**Args:**
 
 - <b>`event_name`</b>:  Name of the juju event to check. 



**Returns:**
 True if the timer is enabled, False otherwise. 



**Raises:**
 
 - <b>`TimerStatusError`</b>:  Timer status cannot be determined. 



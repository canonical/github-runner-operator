<!-- markdownlint-disable -->

<a href="../src/event_timer.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `event_timer.py`
EventTimer for scheduling dispatch of juju event on regular intervals. 



---

## <kbd>class</kbd> `EventConfig`
Configuration used by service and timer templates. 





---

## <kbd>class</kbd> `EventTimer`
Manages the timer to emit juju events at regular intervals. 



**Attributes:**
 
 - <b>`unit_name`</b> (str):  Name of the juju unit to emit events to. 

<a href="../src/event_timer.py#L40"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(unit_name: str)
```

Construct the timer manager. 



**Args:**
 
 - <b>`unit_name`</b>:  Name of the juju unit to emit events to. 




---

<a href="../src/event_timer.py#L99"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `disable_event_timer`

```python
disable_event_timer(event_name: str)
```

Disable the systemd timer for the given event. 



**Args:**
 
 - <b>`event_name`</b>:  Name of the juju event to disable. 



**Raises:**
 
 - <b>`TimerDisableError`</b>:  Timer cannot be stopped. Events will be emitted continuously. 

---

<a href="../src/event_timer.py#L61"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `ensure_event_timer`

```python
ensure_event_timer(
    event_name: str,
    interval: int,
    timeout: Optional[int] = None
)
```

Ensure that a systemd service and timer are registered to dispatch the given event. 

The interval is how frequently, in minutes, that the event should be dispatched. 

The timeout is the number of seconds before an event is timed out. If not given or 0, it defaults to half the interval period. 



**Args:**
 
 - <b>`event_name`</b>:  Name of the juju event to schedule. 
 - <b>`interval`</b>:  Number of minutes between emitting each event. 



**Raises:**
 
 - <b>`TimerEnableError`</b>:  Timer cannot be started. Events will be not emitted. 


---

## <kbd>class</kbd> `TimerDisableError`
Raised when unable to disable a event timer. 





---

## <kbd>class</kbd> `TimerEnableError`
Raised when unable to enable a event timer. 






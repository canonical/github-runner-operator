<!-- markdownlint-disable -->

<a href="../src/database_observer.py#L0"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

# <kbd>module</kbd> `database_observer.py`
Module for observing events related to the database. 



---

## <kbd>class</kbd> `DatabaseObserver`
The Database relation observer. 

<a href="../src/database_observer.py#L16"><img align="right" style="float:right;" src="https://img.shields.io/badge/-source-cccccc?style=flat-square"></a>

### <kbd>function</kbd> `__init__`

```python
__init__(charm: CharmBase, database_name: str)
```

Initialize the observer and register event handlers. 



**Args:**
 
 - <b>`charm`</b> (ops.CharmBase):  The charm instance 
 - <b>`database_name`</b> (str):  The name of the database 


---

#### <kbd>property</kbd> model

Shortcut for more simple access the model. 





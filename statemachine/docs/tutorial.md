## Statemachine Tutorial

_This tutorial covers basic and advanced use of the `statemachine` module._

A statemachine is a relatively simple and intuitive model to add functionality to a class. It can be used in many cases where an object can be in a finite number of states, like:
* a character in a game, where animations are shown depending on actions or transitions between actions (sitting, standing, standing-up),
* a process for administrative records, e.g. customer orders (ordering, ordered, payed, shipped, delivered),
* a button in a user interface that can have multiple states, like a simple checkbox (checked, unchecked, disabled)

On entering, exiting or transitioning between states, actions can be executed through callbacks, that are specific for that state or transition, like showing an animation, committing to a database, sending a message or updating a user-interface.

#### Some Early Tips

* State machines can be visualized in a flow chart. This makes it relatively easy to develop in groups, discuss with non-developers and reach consensus about features and implementation. 
* The sections in this tutorial are ordered by complexity of the functionality. Most state machines do not need nested states (but they are definitely handy when needed). The first sections already allow you to implement a functional state machine,
* All code examples in this tutorial should be runnable (please let me know if they are not).

### Classes

The following classes are part of the public API of the statemachine.

* `StateMachine`: the class where are all functionality of the state machine is defined,
* `StatefulObject(object)`: the class that can be used to make (almost) any python sub-class stateful,
* exception classes:
    * `MachineError(Exception)`: raised in case of a misconfiguration of the state machine,
    * `TransitionError(Exception)`: raised when a non-existing transition is attempted,

### Basics: The Simplest StateMachine

To start off we will show the simplest example of state machine. It defines states and transitions. 
```python
from statemachine.machine import StateMachine, StatefulObject, TransitionError
 
class LightSwitch(StatefulObject):           # inherit from "StatefulObject" to get stateful behaviour        

    machine = StateMachine(  # the statemachine itself is a class parameter of the stateful object here
        states=[
            {"name": "on"},
            {"name": "off"},
        ],
        transitions=[
            {"old_state": "off", "new_state": "on"},
            {"old_state": "on", "new_state": "off"},
        ],
    )

if __name__ == "__main__":
    lightswitch = LightSwitch(initial="off")  # argument "initial" defines the initial state
    assert lightswitch.state == "off"         # the lightswitch is now in the "off" state
        
    lightswitch.state = "on"                  # you can explicitly set the state through the "state" property
    assert lightswitch.state == "on"
    
    lightswitch.state = "off"                 
    assert lightswitch.state == "off"
    
    lightswitch.state = "off"                 # this will not raise an exception, although there is no transition from "off" to "off"
    assert lightswitch.state == "off"
    
    try:
        lightswitch.state = "nix"             # this will raise an exception; there is no state "nix"
    except TransitionError:
        pass
    assert lightswitch.state == "off"
```
Notes:
* The state machine itself is stateless; it does not keep any information about the stateful objects,
* If no `initial` argument to the constructor is given, the first state in the state machine is taken as initial state,
* You can also define the statemachine outside the class and add it in the class definition as class attribute or in the constructor as normal attribute (it is called internally through `self.machine`),
* Another option is to define the arguments to the state machine constructor as a separate dictionary and use it to contruct the state machine `StateMachine(**state_machine_config)`. This configuration can be serialized and persisted or sent over a network (This requires callbacks to be configured as strings).
* By adding a statemachine to a stateful object in its constructor (instead of using a class attribute), you could use different state machines for objects of the same class,
* If any `TransitionError` is raised, the state of the object is returned to the `old_state`.

Although this example adds states and transitions to the LightSwitch object, it does not do much more then protect the object against non-existing states and transitions.

### Basics: Adding triggers

The next step is to add triggers to the state machine. Triggers are methods on the stateful object that cause a transition to take place.  
```python


from statemachine.machine import StateMachine, StatefulObject, TransitionError
 
class LightSwitch(StatefulObject):

    machine = StateMachine(
        states=[
            {"name": "on"},
            {"name": "off"},
        ],
        transitions=[
            {"old_state": "off", "new_state": "on", "triggers": ["turn_on", "flick"]},  # adds 2 triggers for this transition
            {"old_state": "on", "new_state": "off", "triggers": ["turn_off", "flick"]},
        ],
    )

if __name__ == "__main__":
    lightswitch = LightSwitch(initial="off")  # argument "initial" defines the initial state
    assert lightswitch.state == "off"         # the lightswitch is now in the "off" state
    
    lightswitch.turn_on()                     # triggering "turn_on" turns the switch on
    assert lightswitch.state == "on"          # the switch is now "on"
    
    lightswitch.turn_off()                    # turning the switch back off
    assert lightswitch.state == "off"         # the switch is now "off" again
    
    try:
        lightswitch.turn_off()                # cannot turn the switch off, it is already off (and there is no transition "off" to "off")
    except TransitionError:
        pass
    assert lightswitch.state == "off"         # the object is still in a legal state!   
    
    lightswitch.flick()                       # another trigger to change state
    assert lightswitch.state == "on"  
           
    lightswitch.flick()                       # flick() works both ways
    assert lightswitch.state == "off"          
    
```
As you can see, this example already adds a lot of functionality to a class, through a very simple interface. However, this does not enable you to make something happen on a transition (apart from changing state).

Notes:
* Triggers, although they are called as methods, are not actually defined as methods on the class. See `__getattr__` in  `StatefulObject` for more info,
* Instead of using a list of triggers `"triggers": ["turn_on", "flick"]`, you can use a single trigger `"triggers": "turn_on"` if you only need one trigger.


### Basics: Adding Callbacks

To really start using the possibilities of a state machine, callback functions and methods can be added to states and transitions. The main parameters for this are:
* `on_exit`: these functions or methods will be called when the stateful object exits a specific state,
* `on_entry`: functions or methods to be called when the object enters a specific specific state,
* `on_transfer`: functions or methods to be called on a specific transition,
* `before_any_exit`: functions or methods called first, before all transitions within a specific state machine,
* `after_any_entry`: functions or methods called last, after all transitions within a specific state machine.

If the value of the callback parameter is a string, the callback method will be searched in the methods of the stateful class, otherwise the parameter must be a function or method defined elsewhere. These parameters can also be list of strings or functions, which then will be called in order.

In this simple case the signature of the callback must be `func(obj)` with `obj` the stateful object (or `func(self)` in case of a method on the stateful object). Later we will look at passing parameters to the callback.

```python
from statemachine.machine import StateMachine, StatefulObject


def entry_printer(obj):
    print "%s entering state '%s'" % (str(obj), obj.state)

class LightSwitch(StatefulObject):

    machine = StateMachine(
        states=[
            {"name": "on", "on_exit": "exit_printer", "on_entry": entry_printer},
            {"name": "off", "on_exit": "exit_printer", "on_entry": entry_printer},
        ],
        transitions=[
            {"old_state": "off", "new_state": "on", "triggers": "flick", "on_transfer": "transfer"},
            {"old_state": "on", "new_state": "off", "triggers": "flick"},
        ],
        after_any_entry="success"
    )

    def exit_printer(self):
        print "%s exiting state '%s'" % (str(self), self.state)

    def transfer(self):
        print str(self), "flicking"

    def success(self):
        print "it worked"

    def __str__(self):
        return "lightswitch"

if __name__ == "__main__":

    lightswitch = LightSwitch(initial="off")  # setting the initial state does not call any callback functions
    lightswitch.flick()                       # another trigger to change state
    lightswitch.flick()                       # flick() works both ways

    #prints:

    # lightswitch exiting state 'off'
    # lightswitch flicking
    # lightswitch entering state 'on'
    # it worked
    # lightswitch exiting state 'on'
    # lightswitch entering state 'off'
    # it worked
```
Note that again the parameters (`on_exit`, etc.) can be given as a list or a single argument and in case of a list, will be called in order.

### Basics: Callbacks with Arguments
The use fo calbacks can be enhanced by allowing triggers to pass arguments to the callback functions. To avoid confusion about the arguments only keyword arguments are allowed. 
 
The arguments to the trigger method are passed to all the callback functions. The callbacks can ignore arguments by defining **kwargs in their signature.

```python
from statemachine.machine import StateMachine, StatefulObject

class LightSwitch(StatefulObject):

    machine = StateMachine(
        states=[
            {"name": "on", "on_entry": "time_printer"},
            {"name": "off", "on_entry": "time_printer"},
        ],
        transitions=[
            {"old_state": "off", "new_state": "on", "triggers": "flick", "on_transfer": "transfer_printer"},
            {"old_state": "on", "new_state": "off", "triggers": "flick", "on_transfer": "transfer_printer"},
        ],
    )

    def time_printer(self, time, **kwargs):
        print "switch turned %s at %s" % (self.state, str(time))

    def transfer_printer(self, name="who", **kwargs):
        print "%s is using the switch" % name

if __name__ == "__main__":

    from datetime import datetime

    lightswitch = LightSwitch(initial="off")
    lightswitch.flick(name="bob", time=datetime(1999, 12, 31, 23, 59))
    lightswitch.flick(time=datetime(2000, 1, 1, 0, 0))
    
    # prints:
    
    # bob is using the switch
    # switch turned on at 1999-12-31 23:59:00
    # who is using the switch
    # switch turned off at 2000-01-01 00:00:00
```
As you can see it is possible to pass any arguments you require to any callback functions. Note that default arguments (`name="who"`) can be used in the callback functions. 
 
### Basic: Conditional Transitions

Sometimes you want a transition to take place only under specific circumstances. In that case the state machine allows you to set a condition on a transition by setting a parameter `condition`. This condition function must return a value evaluating to `True` if the condition is to take place, and to `False` otherwise.

The implementation has the same features as those for callbacks (it is a callback), including using strings for methods on the stateful object and for passing parameters. It allows only for a single function or method.
```python
from statemachine.machine import StateMachine, StatefulObject


class LightSwitch(StatefulObject):
    machine = StateMachine(
        states=[
            {"name": "on"},
            {"name": "off"},
        ],
        transitions=[
            {"old_state": "off", "new_state": "on", "triggers": "flick", "condition": "is_nighttime"},  # switch only turns on at night
            {"old_state": "on", "new_state": "off", "triggers": "flick"},
        ],
    )

    def __init__(self, *args, **kwargs):
        super(LightSwitch, self).__init__(*args, **kwargs)
        self.daytime = False

    def is_nighttime(self):
        return not self.daytime


if __name__ == "__main__":
    switch = LightSwitch(initial="off") 
    assert switch.is_nighttime()
    switch.flick()
    assert switch.state == "on"
    switch.flick()
    assert switch.state == "off"
    switch.daytime = True
    switch.flick()
    assert switch.state == "off"
```

### Example: Adding a State History

Often it is practical to let a stateful object store a history of all states visited in the past. This can easily be done with the `after_any_entry` callback. As an example we show you how:

```python
from statemachine.machine import StateMachine, StatefulObject

class LightSwitch(StatefulObject):

    machine = StateMachine(
        states=[
            {"name": "on"},
            {"name": "off"},
        ],
        transitions=[
            {"old_state": "off", "new_state": "on", "triggers": "flick"},
            {"old_state": "on", "new_state": "off", "triggers": "flick"},
        ],
        after_any_entry="store_in_history"
    )

    def __init__(self):
        super(LightSwitch, self).__init__()
        self.history = [self.state]  # store the initial state

    def store_in_history(self, **kwargs):
        self.history.append(self.state)

if __name__ == "__main__":

    lightswitch = LightSwitch()
    lightswitch.flick()
    lightswitch.flick()
    lightswitch.flick()
    assert lightswitch.history == ["on", "off", "on", "off"]

```

### Basic: Defining Multiple Transitions

Sometimes many transitions need to be defined with the same end-state and callbacks (e.g. introducing a dead state for unfinished customer orders after a timeout). This can be achieved in 2 simple ways, by either using a wildcard `"*"`, meaning all states or a list of states `["on", "off"].

```python
from statemachine.machine import StateMachine, StatefulObject

class LightSwitch(StatefulObject):

    machine = StateMachine(
        states=[
            {"name": "on", "on_entry": "printer"},
            {"name": "off", "on_entry": "printer"},
            {"name": "broken", "on_entry": "printer"}
        ],
        transitions=[
            {"old_state": "off", "new_state": "on", "triggers": "flick"},
            {"old_state": "on", "new_state": "off", "triggers": "flick"},
            {"old_state": "*", "new_state": "broken", "triggers": "smash"},
            # or: {"old_state": ["on", "off", "broken"], "new_state": "broken", "triggers": "smash"},
            {"old_state": "broken", "new_state": "off", "triggers": "fix"},
        ],
    )

    def printer(self):
        print "entering state '%s'" % self.state


if __name__ == "__main__":

    lightswitch = LightSwitch(initial="off")
    lightswitch.flick()
    lightswitch.smash()
    lightswitch.fix()

    # prints:

    # entering state 'on'
    # entering state 'broken'
    # entering state 'off'

```
Note that only listed states and wildcards can be used for the "from" state (`old_state`) of the transition, since having multiple "to" states would require a condition to determine the state to go to.

---

_At this point you have all the tools to create a functional state machine, including:_
* _defining states and state transitions,_
* _defining triggers that cause state transitions,_
* _defining callbacks on states and state transitions,_
* _passing parameters to the callback functions,_
* _setting a condition on a transition,_
* _using wildcard and listed states to define multiple transitions at once._

_With these elements a fully functional state machine can be implemented. As a state machine grows in complexity or needs to meet additional requirements, the features in the advanced tutorial will become more useful._

---
### Advanced: Switched Transitions

In some cases you might want to transition to different states depending on some condition. This requires a transition with multiple end-states `new_states` and a condition for each end-state.

The example below shows the same lightswitch as we used before, but now, after it breaks and is fixed it returns to the same state is was before breaking.

```python
from statemachine.machine import StateMachine, StatefulObject

class LightSwitch(StatefulObject):

    machine = StateMachine(
        name="matter machine",
        states=[
            {"name": "on"},
            {"name": "off"},
            {"name": "broken"}
        ],
        transitions=[
            {"old_state": "off", "new_state": "on", "triggers": "flick"},
            {"old_state": "on", "new_state": "off", "triggers": "flick"},
            {"old_state": ["on", "off"], "new_state": "broken", "triggers": "smash"},
            {"old_state": "broken", "triggers": "fix", "new_states": [{"name": "on", "condition": "was_on"},
                                                                      {"name": "off"}]},
        ],
        before_any_exit="store_state"  # this callback method is used to store the old state before transitioning
    )

    def __init__(self, initial=None):
        super(LightSwitch, self).__init__(initial=initial)
        self.old_state = None

    def store_state(self):
        self.old_state = self.state

    def was_on(self):
        return self.old_state == "on"

if __name__ == "__main__":
    switch = LightSwitch(initial="off")
    switch.smash()
    switch.fix()
    assert switch.state == "off"

    switch = LightSwitch(initial="on")
    switch.smash()
    switch.fix()
    assert switch.state == "on"
```

Notes:
* The `new_states` must be given in the order you want the conditions to be checked. The first condition that returns a `True` value will let the corresponding transition to take place.
* The last of the `new_states` in the list does not need a `condition` and wil be the default if none of the earlier conditions pass.
* The transition as well as each of the `new_states` parameters can have the `on_transfer` callback; the latter will override the first if the corresponding condition passes.
* If none of the conditions pass, the state of the object does not change,

Explanation: for each state in `new_states` the state machine will create a normal conditional transition. A switched transition is shorthand for a number of conditional transitions.
 
### Advanced: Nested States

When the number of states an object can be in becomes larger, often it is helpful to use nested states. Each state here can be nested, meaning each state can have substates. For substates we use dot-notation; in the example below e.g. "normal.off". The parameters for nested states are the same as for normal states, so each state can have a parameter "states", etc. States can be nested to any level, although more then 3 levels might be excessive.
 
A stateful object always has a complete state, e.g. it cannot be in state "A.B" if "A.B" has substates.
 
Transitions can be defined at any level. So for example a transition from state "A.B.C" to state "E.F" can be defined. A stateful object always has a complete state, e.g. it cannot be in state "A.B" if "A.B" has substates.

Before we go into more detail we will describe a very simple example where the lightswitch has 2 main states "normal" and "broken", The "normal" state has 2 substates "on" and "off". 

```python
from statemachine.machine import StateMachine, StatefulObject


class LightSwitch(StatefulObject):

    machine = StateMachine(
        states=[
            {
                "name": "normal",
                "states": [
                    {"name": "off"},
                    {"name": "on"},
                ],
                "transitions": [
                    {"old_state": "off", "new_state": "on", "triggers": "flick"},
                    {"old_state": "on", "new_state": "off", "triggers": "flick"},
                ]
             },
            {"name": "broken"}
        ],
        transitions=[
            {"old_state": "normal", "new_state": "broken", "triggers": "smash"},
            {"old_state": "broken", "new_state": "normal", "triggers": "fix"},
        ],
    )

if __name__ == "__main__":

    lightswitch = LightSwitch()
    lightswitch.flick()
    lightswitch.smash()
    lightswitch.fix()
    lightswitch.flick()

    assert lightswitch.state == "normal.on"
```
Notes:
* During nested transitions, `on_exit` callbacks are called for all nested states that are exited, starting with the most nested state (e.g. if a lightswitch in state "normal.on" is "broken", first the `on_exit` of the "on" state is called and then the `on_exit` of the "normal" state),
* Similarly during nested transitions, `on_entry` callbacks are called for all nested states that are exited, starting with the least nested state,
* The transition from "normal" to "broken" does not use a complete `old_state` like "normal.off". This transition configures the transition from _any_ sub-state of "normal" to the "broken" state,  
* The transition from "broken" to "normal" does not use complete `new_state` like "normal.on". This transition configures the transition from the "broken" state to the _initial_ (default: first in list) sub-state of the "normal" state, 
* In both case complete states could be used as well to further detail transition configuration, e.g `{"old_state": "broken", "new_state": "normal.off", "triggers": "fix"}`,
* Transitions use relative states, so starting with substates of the state they are defined in,
* Transitions must always be defined at the most nested level, e.g. it raises a MachineError to define a transition `{"old_state": "normal.off", "new_state": "normal.on"}`.

### Advanced: Adding a Context Manager

In some cases, a context manager (`with ... as ...:`) is useful to e.g. only commit to database after a transition is completely succesful. For that purpose an extra callback can be configured in the state machine. The variable returned is passed as keyword argument `context` to all the other callbacks `on_exit`, `on_entry`, etc. Each callback function can choose to ignore the argument (pass it in `**kwargs`).

```python
from contextlib import contextmanager
from statemachine.machine import StateMachine, StatefulObject

class LightSwitch(StatefulObject):

    machine = StateMachine(
        states=[
            {"name": "on"},
            {"name": "off"},
        ],
        transitions=[
            {"old_state": "off", "new_state": "on", "triggers": "flick", "on_transfer": "assert_managed"},
            {"old_state": "on", "new_state": "off", "triggers": "flick", "on_transfer": "assert_managed"},
        ],
        context_manager="do_context"
    )

    def __init__(self):
        super(LightSwitch, self).__init__()
        self.managed = False

    @contextmanager
    def do_context(self, **kwargs):
        self.managed = True
        yield
        self.managed = False

    def assert_managed(self, **kwargs):  # checks if the `managed` attribute is set to True during transition
        assert self.managed


if __name__ == "__main__":

    lightswitch = LightSwitch()
    assert not lightswitch.managed
    lightswitch.flick()
    assert not lightswitch.managed
```

### Example: Multiple State Machines


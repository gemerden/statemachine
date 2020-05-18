## Statemachine Tutorial

---
_This tutorial covers basic and advanced use of the `statemachine` module. Most code examples can be found in the "\examples" folder._

---

A statemachine is a relatively simple and intuitive model to add functionality to a (e.g. orm) class. It can be used in many cases where an object can be in a finite number of states, like:
* a process for administrative records, e.g. customer orders (ordering, ordered, payed, shipped, delivered),
* a button in a user interface that can have multiple states, like a simple checkbox (checked, unchecked, disabled),
* a character in a game, where animations are shown depending on actions or transitions between actions (sitting, standing, standing-up).

On entering, exiting or transitioning between states, actions can be executed through callbacks, that are specific for that state or transition, like showing an animation, committing to a database, sending a message or updating a user-interface.

#### Some Early Tips

* State machines can be visualized in a transition chart. This makes it relatively easy to develop in groups, discuss with non-developers and reach consensus about features and implementation. 
* The sections in this tutorial are ordered by complexity of the functionality. Most state machines do not need nested states (but they are definitely handy when needed). The first sections already allow you to implement a functional state machine,
* All code examples in this tutorial should be runnable (please let me know if they are not).

### Main API

The following functions and classes are part of the public API of the statemachine.

* `state_machine(**config)`: the function returning instances of the correct state machine class,
* `StatefulObject(object)/MultiStateObject(object)`: the class that can be subclassed to make (almost) any python object stateful,
* exception classes:
    * `MachineError(Exception)`: raised in case of a misconfiguration of the state machine,
    * `TransitionError(Exception)`: raised when a state transition fails,

### Basics: The Simplest Statemachine

We will show the simplest example of state machine. It defines states and transitions. 
```python
from states.machine import state_machine, StatefulObject


class LightSwitch(StatefulObject):  # inherit from "StatefulObject" to get stateful behaviour
    machine = state_machine(
        states={
            "on": {},
            "off": {},
        },
        transitions=[
            {"old_state": "off", "new_state": "on", "trigger": "flick"},
            {"old_state": "on", "new_state": "off", "trigger": "flick"},
        ],
    )


if __name__ == "__main__":
    lightswitch = LightSwitch()         # argument "initial" can be use to set the initial state
    assert lightswitch.state == "off"   # the lightswitch is now in the "off" state

    lightswitch.flick()
    assert lightswitch.state == "on"

    lightswitch.flick()
    assert lightswitch.state == "off"
```
Notes:
* The state machine itself is stateless; it does not keep any information about the stateful objects,
* The only attribute used by the state machine on the objects instances is the 'state',
* If no `initial` argument to the constructor is given, the first state in the state machine is taken as initial state,
* You can also define the statemachine outside the class and add it in the class definition as class attribute or in the constructor as normal attribute (it is called internally through `self.machine`),
* One of the main differences between this python3 state machine and the previous version, is that the state cannot be explicitly set ('obj.state = 'some_state'). This lead to a logic inconsistency and was not used in real world cases, 
* Triggers, although they are called as methods, are not actually defined as methods on the class. See `__getattr__` in  `StatefulObject` for details,
* If you need multiple triggers for a transition, you can use a list of trigger names `"trigger": ["turn_on", "flick"]`.

### Basics: Adding Callbacks
The example above does little more than guard against illegal state transitions. To really start using the possibilities of the state machine, we will add some callbacks.

Apart from controling state, the statemachine allows you to call functions (callbacks) before during and after state transitions:    
* `on_exit`: these function(s) or method(s) will be called when the stateful object exits a specific state,
* `on_entry`: called when the object enters a specific specific state,
* `on_transfer`: to be called during a specific transition,
* `before_any_exit`: called first, before all transitions within a specific state machine,
* `after_any_entry`: called last, after all transitions within a specific state machine.

If present, these will be called in this order.

If the value of the callback parameter is a string, the callback will be looked up on the stateful class, otherwise the parameter must be a function defined elsewhere. These parameters can also be list of strings or functions, which will then be called in order.

In this simple case the signature of the callback must be `func(obj)` with `obj` the stateful object (or `func(self)` in case of a method on the stateful object). Later we will look at passing parameters to the callback.

```python
from states.machine import state_machine, StatefulObject


def entry_printer(obj):
    print(f"{str(obj)} entering state '{obj.state}'")

class LightSwitch(StatefulObject):

    machine = state_machine(
        states={
            "on": {"on_exit": "exit_printer", "on_entry": entry_printer},  # string or function
            "off": {"on_exit": "exit_printer", "on_entry": entry_printer},
        },
        transitions=[
            {"old_state": "off", "new_state": "on", "trigger": "flick", "on_transfer": "transfer"},
            {"old_state": "on", "new_state": "off", "trigger": "flick"},
        ],
        after_any_entry="success"
    )

    def exit_printer(self):
        print(f"{str(self)} exiting state '{self.state}'")

    def transfer(self):
        print(f"{str(self)} flicking")

    def success(self):
        print("it worked")

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
The use fo callbacks can be enhanced by allowing triggers to pass arguments to the callback functions. To avoid confusion about the arguments only keyword arguments are allowed. 
 
The arguments to the trigger method are passed to all the callback functions. The callbacks can ignore arguments by defining `*args` and/or `**kwargs` in their signature.

```python
from states.machine import state_machine, StatefulObject

class LightSwitch(StatefulObject):

    machine = state_machine(
        states={
            "on": {"on_entry": "time_printer"},
            "off": {"on_entry": "time_printer"},
        },
        transitions=[
            {"old_state": "off", "new_state": "on", "trigger": "flick", "on_transfer": "name_printer"},
            {"old_state": "on", "new_state": "off", "trigger": "flick", "on_transfer": "name_printer"},
        ],
    )

    def time_printer(self, time, **ignored):
        print(f"switch turned {self.state} at {str(time)}")

    def name_printer(self, name="who", **ignored):
        print(f"{name} is using the switch")

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
As you can see it is possible to pass any arguments you require to any callback functions, by giving the trigger the arguments. By adding `**ignored` (or `**kwargs`) to the callbacks, any unused arguments can be passed but will not be used.

Notes:
* Default arguments (`name="who"`) can be used in the callback functions,
* It is often practical to always give callback functions a `**kwargs` argument, to simplify adding callbacks with different arguments later,
* There are a few other callbacks that can be used. They will be described later in this tutorial.
 
### Basic: Conditional Transitions

Sometimes you want a transition to take place only under specific circumstances. In that case the state machine allows you to set a condition on a state or transition by setting a parameter `condition`. This condition function must return a value evaluating to `True` if the condition is to take place, and to `False` otherwise.

The implementation has the same features as those for callbacks (it is a callback), including using strings to use methods on the stateful object and for passing parameters. If multiple callbacks are given, all callbacks need to return a `True` value for the transition to pass.
```python
from states.machine import state_machine, StatefulObject

class LightSwitch(StatefulObject):
    machine = state_machine(
        states={
            "on": {"condition": "is_nighttime"},
            "off": {},
        },
        transitions=[
            {"old_state": "off", "new_state": "on", "trigger": "flick"},  # switch only turns on at night
            {"old_state": "on", "new_state": "off", "trigger": "flick"},
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
Notes:
* Here we only show the use of condition for entry of a state. Conditions can also be used for specific transitions by adding them to the transition parameters `"condition": callback`.
* If there are multiple transitions with the same starting state and the same trigger, but different end-states. Conditions are evaluated in order the states and transitions are configured in the state machine.
* If both a state and a transition to that state have a condition, both need to be true for the transition to take place.

### Example: Adding a State History

Often it is practical to let a stateful object store a history of all states visited in the past. This can easily be done with the `after_any_entry` callback. As an example we show you how:

```python
from states.machine import state_machine, StatefulObject

class LightSwitch(StatefulObject):

    machine = state_machine(
        states={
            "on": {},
            "off": {},
        },
        transitions=[
            {"old_state": "off", "new_state": "on", "trigger": "flick"},
            {"old_state": "on", "new_state": "off", "trigger": "flick"},
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
---

_At this point you have all the tools to create a functional state machine, including:_
* _defining states and state transitions,_
* _defining triggers that cause state transitions,_
* _defining callbacks on states and state transitions,_
* _passing parameters to the callback functions,_
* _setting a condition on a transition,_

_With these elements a fully functional state machine can be implemented. As a state machine grows in complexity or needs to meet additional requirements, the features in the advanced tutorial will become more useful._

---

### Advanced: Overriding Triggers

It is possible to directly trigger a transition on the state machine itself, possibly to reduce the complexity of your stateful object API. 

In this case we implement the `flick` trigger method ourselves, to be able to update the stateful object without introducing a new method name (`flick` is already defined in the state machine, it now first updates the object):

```python
from states.machine import state_machine, StatefulObject

class LightSwitch(StatefulObject):
    machine = state_machine(
        states={
            "on": {},
            "off": {},
        },
        transitions=[
            {"old_state": "off", "new_state": "on", "trigger": "flick", "condition": "is_night"},  # switch only turns on at night
            {"old_state": "on", "new_state": "off", "trigger": "flick"},
        ],
    )

    def __init__(self, time=0, *args, **kwargs):
        super(LightSwitch, self).__init__(*args, **kwargs)
        self.time = time

    def flick(self, hours_later, *args, **kwargs):  # *args, **kwargs are only added to show passing arguments to the machine
        self.time = (self.time + hours_later)%24    # increment time with hours and start counting from 0 if >24 (midnight)
        self.machine.trigger(self, "flick", *args, **kwargs)  # use the trigger name to call the trigger method on the state machine

    def is_night(self):
        return self.time < 6 or self.time > 18


if __name__ == "__main__":
    switch = LightSwitch(time=0, initial="on")
    assert switch.is_night()
    switch.flick(hours_later=7)  # switch.time == 7
    assert switch.state == "off"
    switch.flick(hours_later=7)  # switch.time == 14
    assert switch.state == "off"
    switch.flick(hours_later=7)  # switch.time == 21
    assert switch.state == "on"

```
Note that `flick` has a `hours` argument that is not passed to the state machines `trigger' method.

### Advanced: Defining Multiple Transitions

Sometimes many transitions need to be defined with the same end-state and callbacks (e.g. introducing a dead state for unfinished customer orders after a timeout). This can be achieved in 2 simple ways, by either using a wildcard `"*"`, meaning all states or a list of states `["on", "off"].

Note that if multiple states are given for `new_state`, no triggers can be defined for the transition; a `MachineError` will be raised. This means that the transition can only take place bij explicitly giving the state `obj.state = "some_state"` (no parameters can be passed to the callbacks in these cases).
```python
from states.machine import state_machine, StatefulObject

class LightSwitch(StatefulObject):

    machine = state_machine(
        states={
            "on": {"on_entry": "printer"},
            "off": {"on_entry": "printer"},
            "broken": {"on_entry": "printer"}
        },
        transitions=[
            {"old_state": "off", "new_state": "on", "trigger": "flick"},
            {"old_state": "on", "new_state": "off", "trigger": "flick"},
            {"old_state": "*", "new_state": "broken", "trigger": "smash"},
            # or: {"old_state": ["on", "off", "broken"], "new_state": "broken", "trigger": "smash"},
            {"old_state": "broken", "new_state": "off", "trigger": "fix"},
        ],
    )

    def printer(self):
        print(f"entering state '{self.state}'")


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

### Advanced: Switched Transitions

In some cases you might want to transition to different states depending on some condition. This requires a transition with multiple end-states `new_state` and a condition for each end-state.

The example below shows the same lightswitch as we used before, but now, after it breaks and is fixed it returns to the same state is was before breaking.

```python
from states.machine import state_machine, StatefulObject

class LightSwitch(StatefulObject):

    machine = state_machine(
        name="matter machine",
        states={
            "on": {},
            "off": {},
            "broken": {}
        },
        transitions=[
            {"old_state": "off", "new_state": "on", "trigger": "flick"},
            {"old_state": "on", "new_state": "off", "trigger": "flick"},
            {"old_state": ["on", "off"], "new_state": "broken", "trigger": "smash"},
            {"old_state": "broken", "trigger": "fix", "new_state": {"on": {"condition": "was_on"},
                                                                     "off": {}}},
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
* The `new_state` must be given in the order you want the conditions to be checked. The first condition that returns a `True` value will let the corresponding transition to take place.
* The last of the `new_state` in the list does not need a `condition` and wil be the default if none of the earlier conditions pass.
* The transition as well as each of the `new_state` parameters can have the `on_transfer` callback; if both are present, both are called,
* If none of the conditions pass, the state of the object does not change,

Behind the scenes: for each state in `new_state` the state machine will create a normal conditional transition. A switched transition is shorthand for a number of conditional transitions.
 
### Advanced: Multiple States

Sometimes the problem at hand requires an object to have multiple relatively unrelated states. Think of a person with a 
marital state (maried, unmaried, ..) and an employment status (employed, unemployed, sick, ...).

To model this the object (person) can have multiple state machines, as shown in the simple exampe below (note the different baseclass): 

 
```python
from states.machine import state_machine, MultiStateObject

class MoodyColor(MultiStateObject):
    color = state_machine(
        states=dict(
            red={'on_entry': 'on_entry'},
            blue={'on_entry': 'on_entry'},
        ),
        transitions=[
            dict(old_state='red', new_state='blue', trigger='next'),
            dict(old_state='blue', new_state='red', trigger='next'),
        ],
    )
    mood = state_machine(
        states=dict(
            good={'on_entry': 'on_entry'},
            bad={'on_entry': 'on_entry'},
        ),
        transitions=[
            dict(old_state='good', new_state='bad', trigger='next'),
            dict(old_state='bad', new_state='good', trigger='next'),
        ],
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_call = None
        self.counter = 0

    def on_entry(self, call_name):
        self.last_call = call_name
        self.counter += 1

if __name__ == "__main__":

    moodycolor = MoodyColor()
    moodycolor.next('next')
    assert moodycolor.state == {'color': 'blue', 'mood': 'bad'}
    assert moodycolor.color == 'blue'
    assert moodycolor.mood == 'bad'
    assert moodycolor.last_call == 'next'
    assert moodycolor.counter == 2
```
Notes:
* As you can see above, calling 'next' will make transition in both state machines occur, because both transitions define 'next' as trigger,
* Getting an attribute with a state machine name (like 'moodycolor.mood') will return the state with respect to that state machine ('bad'),
* Callbacks defined with a string are still looked up on the object; ofcourse different callbacks can be defined for each state machine,
* Setting a custom initial state (top state of machine.states is default initial state), requires a dictionary like '{'color': 'blue', 'mood': 'bad'}'.

### Advanced: Nested States

When the number of states an object can be in becomes larger, often it is helpful to use nested states. Each state here can be nested, meaning each state can have substates. 

For substates we use dot-notation; in the example below e.g. "normal.off". The parameters for nested states are the same as for normal states, so each state can again have a parameter "states". States can be nested to any level, although more then 3 levels might be excessive.

First some rules:
1. A stateful object always has a complete state, e.g. it cannot be in state "A.B" if "A.B" has substates.
2. Transitions can be defined at any level. So for example a transition from state "A.B.C" to state "E.F" can be defined,
3. However a transition like "A.B" to "A.C" cannot be defined in the top level state machine; it must be defined within state machine "A".

Before we go into more detail we will describe a very simple example where the lightswitch has 2 main states "normal" and "broken", The "normal" state has 2 substates "on" and "off". 

```python
from states.machine import state_machine, StatefulObject


class LightSwitch(StatefulObject):
    machine = state_machine(
        states={"normal": {
                    "states": {
                        "off": {},
                        "on": {},
                    },
                    "transitions": [
                        {"old_state": "off", "new_state": "on", "trigger": "flick"},
                        {"old_state": "on", "new_state": "off", "trigger": "flick"},
                    ]
                },
                "broken": {}
        },
        transitions=[
            {"old_state": "normal", "new_state": "broken", "trigger": "smash"},
            {"old_state": "broken", "new_state": "normal", "trigger": "fix"},
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
* In both case complete states could be used as well to further detail transition configuration, e.g `{"old_state": "broken", "new_state": "normal.off", "trigger": "fix"}`,
* Transitions use relative states, so starting with substates of the state they are defined in,
* Transitions must always be defined at the most nested level, e.g. it raises a MachineError to define a transition `{"old_state": "normal.off", "new_state": "normal.on"}`,
* The state attribute of the stateful object is updated during a transition, e.g. going from "normal.on" to 'broken', the state attribute will go from 'normal.on' to 'normal' to 'broken', following the call order of e.g. the `on_exit` callbacks,

### Advanced: Adding a Context Manager

In some cases, a context manager (`with ... as ...:`) is useful to e.g. only commit to database after a transition is completely succesful. For that purpose an extra callback can be configured in the state machine. The variable returned is passed as keyword argument `context` to all the other callbacks `on_exit`, `on_entry`, etc. Each callback function can choose to ignore the argument (pass it in `**kwargs`).

```python
from contextlib import contextmanager
from states.machine import state_machine, StatefulObject

class LightSwitch(StatefulObject):

    machine = state_machine(
        states={
            "on": {},
            "off": {},
        },
        transitions=[
            {"old_state": "off", "new_state": "on", "trigger": "flick", "on_transfer": "assert_managed"},
            {"old_state": "on", "new_state": "off", "trigger": "flick", "on_transfer": "assert_managed"},
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
Notes:
* If multiple context managers are used in nested state machines, only the innermost context manager will be invoked. This might be changed in future releases.

### Other Examples

Currently there are two more code examples in the 'examples' directory:
1. One shows the use of multiple state machines interacting. 
2. The other is an example of a simple graphical mood simulation, using [pygame](https://www.pygame.org/).

Although these examples work, they are pretty undocumented at the moment.




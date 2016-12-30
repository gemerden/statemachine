## Statemachine Tutorial

A statemachine is a relatively simple and intuitive model to add functionality to a class. It can be used in many cases where an object can be in a finite number of states, like:
* a character in a game, where animations are shown depending on actions or transitions between actions (sitting, standing, standing-up),
* a process for administrative records, e.g. customer orders (ordering, ordered, payed, shipped, delivered),
* a button in a user interface that can have multiple states, like a simple checkbox (checked, unchecked, disabled)

On entering, exiting or transitioning between states, actions can be executed through callabacks, that are specific for that state or transition, like showing an animation, committing to a database, sending a message or updating a user interface.

#### Some Early Tips

* State machines can be visualized in a flow chart. This makes it relatively easy to develop in groups, discuss with non-developers and reach consensus about domain and implementation. 
* The sections in this tutorial are ordered by complexity of the functionality. Most state machines do not need nested states (but they are definitely handy when needed). The first 2 sections already allow you to implement a functional state machine,
* All code examples in this tutorial should be runnable (please let me know if they are not).

### Classes

The following classes are part of the public API of the statemachine.

* `StateMachine`: the class where are all functionality of the state machine is defined,
* `StatefulObject(object)`: the class that can be used to make (almost) any python sub-class stateful,
* exception classes:
    * `MachineError(Exception)`: raised in case of a misconfiguration of the state machine,
    * `TransitionError(Exception)`: raised when a non-existing transition is attempted,

### The Simplest StateMachine

To start off we will show the simplest example of state machine. It defines states and transitions. 
```python
from statemachine.baseclass import StatefulObject
from statemachine.machine import StateMachine, TransitionError
 
class LightSwitch(StatefulObject):           # inherit from "StatefulObject" to get stateful behaviour        

    machine = StateMachine(
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
        lightswitch.state = "nix"             # this will not raise an exception; there is no state "nix"
    except TransitionError:
        pass
    assert lightswitch.state == "off"
```
Although this example adds states and transitions to the LightSwitch object, it does not do much more then protect the object against non-existing states and transitions.

### Adding triggers

The next step is to add triggers to the state machine. Triggers are methods on the stateful object that cause a transition to take place.  
```python
from statemachine.baseclass import StatefulObject
from statemachine.machine import StateMachine, TransitionError
 
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


### Adding Callbacks

To really start using the possibilities of a state machine, callback functions and methods can be added to states and transitions. The main parameters for this are:
* `on_exit`: these functions or methods will be called when the stateful object exits a specific state,
* `on_entry`: functions or methods to be called when the object enters a specific specific state,
* `on_transition`: functions or methods to be called on a specific transition,

If the value of the callback parameter is a string, the callback method will be searched in the methods of the stateful class, otherwise the parameter must be a function or method defined elsewhere.

In this simple case the signature of the callback must be `func(obj)` with `obj` the stateful object (or `func(self)` in case of a method on the stateful object). Later we will look at passing parameters to the callback.

```python
from statemachine.baseclass import StatefulObject
from statemachine.machine import StateMachine

def entry_printer(obj):
    print "%s entering state '%s'" % (str(obj), obj.state)

class LightSwitch(StatefulObject):

    machine = StateMachine(
        states=[
            {"name": "on", "on_exit": "exit_printer", "on_entry": entry_printer},
            {"name": "off", "on_exit": "exit_printer", "on_entry": entry_printer},
        ],
        transitions=[
            {"old_state": "off", "new_state": "on", "triggers": "flick", "on_transfer": "going"},
            {"old_state": "on", "new_state": "off", "triggers": "flick"},
        ],
    )

    def exit_printer(self):
        print "%s exiting state '%s'" % (str(self), self.state)

    def going(self):
        print str(self), "flicking"

    def __str__(self):
        return "lightswitch"

if __name__ == "__main__":

    lightswitch = LightSwitch(initial="off")  # setting the initial state does not call any callback functions    
    lightswitch.flick()                       # will call obj.exit_printer(), obj.going() and entry_printer(obj) respectively
    lightswitch.flick()                       # flick() works both ways
             
    # this will print:
    
    # lightswitch exiting state 'off'
    # lightswitch flicking
    # lightswitch entering state 'on'
    # lightswitch exiting state 'on'
    # lightswitch entering state 'off'

```
Note that again the parameters (`on_exit`, etc.) can be given as a list or a single argument and in case of a list, will be called in order.

### Callbacks with Arguments

### More on Callbacks

### Conditional Transitions

### Wildcard & List Transitions

### Switched Transitions

### Nested States

### Adding a Context Manager

### Adding a State History


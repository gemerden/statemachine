### Statemachine Tutorial

A statemachine is a relatively simple and intuitive model to add functionality to a class. It can be used in many cases where an object can be in a finite number of states, like:
* a character in a game, where animations are shown depending on actions or transitions between actions (sitting, standing, standing-up),
* a process an administrative record goes through, e.g. a customer order (ordering, ordered, payed, shipped, delivered),
* a button in a user interface that can have multiple states, like a simple checkbox (checked, unchecked, disabled)

On entering, exiting or transitioning between states, actions can be executed through callabacks, that are specific for that state or transition, like showing an animation, committing to a database, sending a message or updating a user interface.

##### Some Notes

* The sections in this tutorial are ordered by complexity of the functionality. Most state machines do not need nested states (but they are definitely handy when needed). The first 2 sections already allow you to implement a functional state machine.

#### Classes

The following classes are part of the public API of the statemachine.

* `StateMachine`: the class where are all functionality of the state machine is defined,
* `StatefulObject(object)`: the class that can be used to make (almost) any python sub-class stateful,
* exception classes:
    * `MachineError(Exception)`: raised in case of a misconfiguration of the state machine,
    * `TransitionError(Exception)`: raised when a non-existing transition is attempted,

## The Simplest StateMachine

To start off we will show the simplest example of  state machine. It defines states, transitions and triggers and will raise exception when illegal transitions are attempted. 
```python
from statemachine.baseclass import StatefulObject
from statemachine.machine import StateMachine
 
class LightSwitch(StatefulObject):

    machine = StateMachine(
        states=[
            {"name": "on"},
            {"name": "off"},
        ],
        transitions=[
            {"old_state": "off", "new_state": "on", "triggers": ["turn_on", "flick"]},
            {"old_state": "on", "new_state": "off", "triggers": ["turn_off", "flick"]},
        ],
    )

if __name__ == "__main__":
    lightswitch = LightSwitch(initial="off")  # argument "initial" defines the initial state
    assert lightswitch.state == "off"         # the lightswitch is now in the "off" state
    lightswitch.turn_on()                     # turning the switch on
    assert lightswitch.state == "on"          # the switch is now "on"
    lightswitch.flick()                       # another trigger to change state
    assert lightswitch.state == "off"         
    lightswitch.flick()                       # flick() works both ways
    assert lightswitch.state == "on"          
    lightswitch.state = "off"
    assert lightswitch.state == "off"
```


## Adding Callbacks

```python
def printer(obj):
    print "'%s' with state '%s'" % (str(obj), obj.state)

class LightSwitch(StatefulObject):

    machine = StateMachine(
        states=[
            {"name": "on", "on_exit": printer, "on_entry": printer},
            {"name": "off", "on_exit": printer, "on_entry": printer},
        ],
        transitions=[
            {"old_state": "off", "new_state": "on", "triggers": ["turn_on", "switch"]},
            {"old_state": "on", "new_state": "off", "triggers": ["turn_off", "switch"]},
        ],
    )

```

## Callbacks with Arguments

## Conditional Transitions

## Wildcard & Listed Transitions

## Switched Transitions

## Nested States


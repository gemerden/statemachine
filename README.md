# statemachine
Easy to use state machine to manage the state of python objects.

Note: this is the python >= 3.6 version of the module. For the previous version see branch "states2". This version is not backward compatible (it uses the ordered dicts introduced in python 3.6)

## Introduction
This state machine implementation is developed with the following goals in mind:

* Easy to use API, for configuration of the state machine and triggering state transitions,
* Usable for any (almost, I'm sure) python class with a finite number of states,
* Fully featured, including nested states, conditional transitions, shorthand notations, many ways to configure callbacks,
* Simple state machines do not require advanced knowledge; complexity of configuration scales with complexity of requirements, 
* One state machine instance can manage the state of many stateful objects; the objects only store their current state string,
* Option to use multiple state machines in the same class,
* Fast and memory efficient.

## Installation
To install the module you can use: `pip install states3`

## Versions
This is a new section of the readme, starting with version 0.4.0.

####Version 0.4.1:

**Bug fixes**
- fixed incorrect calling of `on_exit` in some cases. Introduced in 0.3.2. Do upgrade if you can.

####Version 0.4.0:


**Features**
 - trigger calls now return the object itself, making them idempotent: `object.trigger1().trigger2()` works,
 - added an `on_stay` callback option to states, called when a trigger is called which results in the state not changing. This and `on_transfer` are the only callbacks being called in such a case.
 
**Bug fixes**
- no current bugs, please inform me if any are found
  
**Changes**
 - when no transition takes place on a trigger call, `on_exit`, `on_entry` etc. are not called anymore (`on_transfer` will be if defined). `on_stay` can be used to register callbacks for this case. This breaks backward-compatibility in some cases, but in practice makes the definition of the state machine a lot easier when calling `on_exit` etc. is undesirable when the actual state does not change. It makes configuration also a lot more intuitive (at least for me ;-).
 - trigger calls do not return whether a state change has taken place (a `bool`), but the object on which the trigger was called, making them idempotent.
 
 

## Code Example

Here is a simple statemachine to give some idea of what the configuration looks like.
```python
from states import state_machine, StatefulObject

class LightSwitch(StatefulObject):
    machine = state_machine(
        states={
            "on": {"info": "see the light"},
            "off": {"info": "stay in dark"},
        },
        transitions=[
            {"old_state": "off", "new_state": "on", "trigger": "flick"},
            {"old_state": "on", "new_state": "off", "trigger": "flick"},
        ],
        after_any_entry="print"  # after entering any state method 'print' is called 
    )

    def print(self, name):
        print(f"{name} turned the light {self.state}")    
    
lightswitch = LightSwitch(initial="off") 
lightswitch.flick(name="Bob")  # prints: "Bob turned the light on"                 
```


## Limitations
The state machine module 'states3' with python version below 3.6.

## Documentation
To learn more check the extensive [tutorial](https://github.com/gemerden/statemachine/blob/master/statemachine/docs/tutorial.md).

## Concepts
The following basic state machine concepts are used

* *state*: state of an stateful object; objects can be in one state at the time,
* *transition*: transition of the object from one state to another resulting,
* *state machine*: system that manages the states of objects according to predefined states and transitions,
* *trigger*: method called on an object that can result in a state transition,
* *callbacks*: functions called on state transitions by the state machine,
* *condition*: conditions for a specific state transition to take place.

## Features
The module has the following basic and some more advanced features:

* enable triggering state transitions by setting trigger name(s) in machine configuration:
    * same trigger can be set for different transitions,
    * trigger method can pass arguments to callbacks like `on_exit` and `on_entry`,
* conditions (and callbacks) can be set on states and transitions:
    * if a transition is triggered, but the condition is not met, the transition does not take place
* switched transitions can be used to go from one state to another depending on conditions
    * trigger can be used for conditional (switched) transition,
    * to do this, create multiple transitions from the same state to different states and give them different conditions
* a number of callbacks can be installed for each state and transition, with obj the state managed object and **kwargs the arguments passed via the trigger to the callback, in calling order:
    * `StateMachine.prepare(self, obj, **kwargs)` (will always be called),
    * `StateMachine.before_any_exit(self, obj, **kwargs)`,
    * `State.on_exit(self, obj, **kwargs)`,
    * `Transition.on_transfer(self, obj, **kwargs)`, # after this the state is changed on the object
    * `State.on_entry(self, obj, **kwargs)`,
    * `StateMachine.after_any_entry(self, obj, **kwargs)`
    * note that if a condition is present and not met, the object will stay in its state and an optional callback `State.on_stay` will be called.
* callbacks can be methods on the class of which the state is managed by the machine:
    * This is the case the calback is configured as a string (e.g. `"on_entry": "do_callback"`) that is looked op on the stateful class,
* wildcards and listed states can be used to define multiple transitions at once:
    * e.g. transition `{"old_state": ["A", "B"], "new_state": "C"}` would create 2 transitions from A and B to C,
* nested states can be used to better organize states and transitions, states can be nested to any depth,
* multiple state machines can be used in the same class and have access to that class for callbacks,
* context managers can be used to create a context for all callbacks,
* custom exceptions:
    * MachineError: raised in case of a misconfiguration of the state machine,
    * TransitionError: raised in case of e.g. an attempt to trigger a non-existing transition,


## Rules (for the mathematically minded)
The state machine in the module has the following rules for setting up states and transitions:

* notation:
    * A, B, C  : states of a state managed object (called 'object' from now)
    * A(B, C) : state A with nested states B, C, with * indicating that B is the default initial state
    * A.B : sub-state B of A; A.B is called a state path
    * <A, B>   : transition between state A and state B
    * <A, B or C>: transition from A to B or C, depending on condition functions (there is no 'and')
    * <A, *>: shorthand for all transitions from A to states in the same machine
* an object cannot just be in state A if A has substates; given state A(B, C), the object can be in A.B or A.C, not in A
* allowed transitions, given states A,  B, C(E, F) and D(G, H):
    * <A, B>: basic transition, configured as {"old_state": "A", "new_state": "B"}
    * <A, A>: transition from a state to itself
    * <C.E, A>: transition from a specific sub-state of C to A
    * <C, D.G>: transition from any sub-state of C to specific state D.G
    * <A, C>: transition from A to C.E, E being the initial state of C because it was explicitly set or because it is the first state in E
    * <C.F, D.H>: transitioning from one sub-state in a state to another sub-state in another state. Note that this would call (if present) on_exit on F and C and on_entry on D and H in that order.
* non-allowed transitions:
    * <C.E, C.F>: inner transitions cannot be defined on the top level; define <E, F> in state C
* adding switched transitions, given transition <A, B or C or D>:
    * B and C must have conditions attached in the transition, these condition will be run though in order
    * D does not need to have a condition attached meaning it will always be the next state if the conditions on the transition to B and C fail

## Authors

Lars van Gemerden (rational-it) - initial code and documentation.

## License

See LICENSE.txt.



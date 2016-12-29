# Statemachine Tutorial

## Introduction

* No need to read all for simple cases.

## Classes

* `StateMachine`
* `StatefulObject`
* exceptions:
    * `MachineError`: raised in case of a misconfiguration of the state machine,
    * `TransitionError`: raised in case of e.g. an attempt to trigger a non-existing transition,
    * `SetStateError`: raised when obj.state = "some_state" fails

### Public Classes

### Internal Classes

## The Simplest StateMachine

### Example

```python
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

```

###Explanation

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


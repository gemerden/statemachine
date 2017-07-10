![Travis](https://travis-ci.org/gemerden/statemachine.svg?branch=master)

# statemachine
Easy to use state machine to manage the state of python objects.

## Introduction
This state machine implementation is developed with the following goals in mind:

* Easy to use API, for configuration of the state machine and triggering state transitions,
* Usable for any (almost, I'm sure) python class with a finite number of states,
* Fully featured, including nested states, conditional transitions, shorthand notations, many ways to configure callbacks,
* Simple state machines do not require advanced knowledge; complexity of configuration scales with complexity of requirements, 
* One state machine instance can manage the state of many stateful objects; the objects only store their current state string,
* Reasonably fast

## Limitations
The state machine module has been tested with python 2.7, if requested I will definitely consider python 3 support, depending on time constraints.

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

* trigger state transitions by setting trigger name in machine configuration:
    * same trigger can be set for different transitions,
    * trigger method can pass arguments to callbacks like `on_exit` and `on_entry`,
* conditions (also callbacks) can be set on states and transitions:
    * if a transition is triggered, but the condition is not met, the transition does not take place
* switched transitions can be used to go from one state to another depending on conditions
    * trigger can be used for conditional (switched) transition,
    * to do this, create multiple trasnitions from the same state to different states and give them different conditions
* state transitions can be started by explicitly setting the state (obj.state = "some_state"):
    * if a condition is set and not met on the transition an exception is raised, because the callbacks would not be called,
    * if the callbacks function require extra arguments (apart from the state managed object), this method will fail
* a number of callbacks can be installed for each state and transition, with obj the state managed object and **args, ***kwargs the arguments passed via the trigger to the callback, in calling order:
    * StateMachine.prepare(self, obj. **args, ***kwargs),
    * StateMachine.before_any_exit(self, obj. **args, ***kwargs),
    * State.on_exit(self, obj. **args, ***kwargs),
    * Transition.on_transfer(self, obj. **args, ***kwargs), # after this the state is changed on the object
    * State.on_entry(self, obj. **args, ***kwargs),
    * StateMachine.after_any_entry(self, obj. **args, ***kwargs)
    * note that if a condition is present and not met, none of these functions are called, apart from prepare
* callbacks can be methods on the class of which the state is managed by the machine:
    * This is the case when the calback is configured as a string (e.g. "on_entry": "do_callback"),
* wildcards and listed states can be used to define multiple transitions at once:
    * e.g. transition {"old_state": "*", "new_state": ["A", "B"]} would create transitions from all states to both state A and B
* nested states can be used to better organize states and transitions, states can be nested to any depth,
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
    * <A, [B, C]>: shorthand for transitions <A, B> and <A, C>
    * <A, *>: shorthand for all transitions from A to states in the same machine
* an object cannot just be in state A if A has substates; given state A(B, C), the object can be in A.B or A.C, not in A
* allowed transitions, given states A,  B, C(E, F) and D(G, H):
    * <A, B>: basic transition, configured as {"old_state": "A", "new_state": "B"}
    * <A, A>: transition from a state to itself
    * <C.E, A>: transition from a specific sub-state of C to A
    * <C, D.G>: transition from any sub-state of C to specific state D.G
    * <A, C>: transition from A to C.E, E being the initial state of C because it was explicitly set or because it is the first state in E
    * <C.F, D.H>: transitioning from one sub-state in a state to another sub-state in another state. Note that:
* non-allowed transitions:
    * <C.E, C.F>: inner transitions cannot be defined on the top level; define <E, F> in state C
* adding switched transitions, given transition <A, B or C or D>:
    * B and C must have conditions attached in the transition, these condition will be run though in order
    * D does not need to have a condition attached meaning it will always be the next state if the conditions on the transition to B and C fail



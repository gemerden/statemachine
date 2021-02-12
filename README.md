# StateMachine
Easy to use state machine to manage the state of python objects.


## Introduction
This state machine implementation is developed with the following goals in mind:

* Easy to use API, for configuration of the state machine and triggering state transitions,
* Usable for any (almost, I'm sure) python class with a finite number of states,
* Fully featured, including nested states, conditional transitions, shorthand notations, many ways to configure callbacks,
* Simple state machines do not require advanced knowledge; complexity of configuration scales with complexity of requirements, 
* One state machine manages the state of all instances of a class; the objects only store their current state as a string,
* Option to use multiple interacting state machines in the same class, with no added complexity,
* Fast and memory efficient.

## Installation
To install the module you can use: `pip install states3`

## Limitations
This module only runs on Python >= 3.6.

## Code Example

Here is a simple statemachine to give some idea of what the configuration looks like.
```python
from states import state_machine, StatefulObject, states, state, transition

class LightSwitch(StatefulObject):
    state = state_machine(
        states=states('off', 'on'),
        transitions=[
            transition('off', 'on', trigger='flick'),
            transition('on', 'off', trigger='flick'),
        ],
    )
    
    @state.on_entry('on', 'off')
    def print(self, name):
        print(f"{name} turned the light {self.state}")    
    
lightswitch = LightSwitch(state="off") 
lightswitch.flick(name="Bob")  # prints: "Bob turned the light on"                 
```
> Note that this configuration works for the versions >= 0.5.0.

## Concepts
The following basic state machine concepts are used:

* *state machine*: system that manages the states of objects according to predefined states and transitions,
* *state*: state of an stateful object; objects can be in one state at the time,
* *transition*: transition of the object from one state to another,
* *trigger*: (generated) method called on an object that triggers a state transition,
* *callback*: different functions called on state transitions by the state machine,
* *condition*: conditions that allow a specific state transition to take place.

## Features
The module has the following basic and some more advanced features:

* enable _triggering_ state transitions by setting trigger name(s) in machine configuration:
    * same trigger can be set for different transitions,
    * when a trigger method is called it passes its arguments to all callbacks (e.g. `on_exit`, `on_entry`),
* _conditional transitions_ can be used to change state depending on condition functions,
    * if a transition is triggered, but the condition is not met, the transition does not take place
    * to do this, create multiple transitions from the same state to different states and give them different conditions
* a number of _callbacks_ can be installed for each state and transition, with obj the state managed object and **kwargs the arguments passed via the trigger to the callback, in calling order:
    * `Machine.prepare(self, *args, **kwargs)`,
    * `State.on_exit(self, *args, **kwargs)`,
    * `Transition.on_transfer(self, *args, **kwargs)`,
    * `State.on_entry(self, *args, **kwargs)`,
    * `State.parent.on_stay(self, *args, **kwargs)`,
    * note that if a condition is present and not met, the object will stay in its state and an optional callback `State.on_stay` will be called.
* _callbacks_ can be methods on the class of which the state is managed by the machine:
    * This is the case the calback is configured as a string (e.g. `"on_entry": "do_callback"`) that is looked op on the stateful class,
* _wildcards_ (`*`) and listed states can be used to define (callbacks for) multiple transitions or at once:
    * e.g. transition `transition(["A", "B"], "C")` would create 2 transitions, on from A to C and one from B to C,
* _nested_ states can be used to better organize states and transitions, states can be nested to any depth,
* _multiple_ state machines can be used in the same class and have access to that class for callbacks,
* a _context manager_ can be defined on state machine level to create a context for each transition,
* custom _exceptions_:
    * MachineError: raised in case of a misconfiguration of the state machine,
    * TransitionError: raised in case of e.g. an attempt to trigger a non-existing transition,

---

## Example
 This section we will show an example that shows most of the features of the state machine. We will introduce features step-by-step. 
 
 Lets define a User in the context of getting access to a web app:
 
 ```python
from states import StatefulObject

class User(StatefulObject):
    
    def __init__(self, email, **kwargs):
        super().__init__(**kwargs)
        self.email = email
        self.password = None
    
```
We will keep the user class simple for clarity sake. No password hashing, tokens, etc.

Notice the base class `StatefulObject`: it sets one class attribute and adds trigger methods to the `User` class when these are defined.

Now let's add a state machine to the 'User':

 ```python
from states import StatefulObject, state_machine

class User(StatefulObject):
    state = state_machine(...)

    def __init__(self, username, state='somestate'):
        super().__init__(state=state)
        self.username = username
        self.password = None
```
 
* `state_machine` is the factory function that takes a configuration and turns it in a fully fledged state machine.
* Notice you can set the initial state through the `state` (name of the state machine), argument of `__init__`.

lets add some states: 
* `new`: a user that has just been created, without password, etc.
* `active`: a user that is active on the server, has been authenticated at least once, ...
* `blocked`: a user that has been blocked access for whatever reason.

 ```python
from states import StatefulObject, state_machine, states

class User(StatefulObject):
    state = state_machine(
        states=states('new', 'active', 'blocked')
    )

    def __init__(self, username):
        super().__init__(state='new')
        self.username = username
        self.password = None
```
 
* `state_machine` takes a parameter `states`, preferable created with the `states` function that returns a validated dictionary.
* The initial state can be set as above; if not given, the first state of the state machine will be the initial state,
* Note that the state_machine `state` can have any other name.

Next we will add transitions to the state machine to get a working state machine:

```python
from states import StatefulObject, state_machine, states, transition

class User(StatefulObject):
    state = state_machine(
        states=states('new', 'active', 'blocked'),
        transitions=[
            transition('new', 'active', trigger='activate'),
            transition('active', 'blocked', trigger='block'),
            transition('blocked', 'active', trigger='unblock'),
        ]   
    )

    def __init__(self, username):
        super().__init__(state='new')
        self.username = username
        self.password = None

user = User('rosemary')
user.activate()
assert user.state == 'active'  # this is the current state of the user
```

* We add a an argument `transitions` to the state machine with from- and to states, and a trigger name that can be called to trigger the transition.
* The `transition` items in the `transitions` list are validating functions returning a dictionary,
* The transitions limit the possible transition between states to those with transitions defined on them; if e.g. `user.activate()` was called again, a `TransitionError` would be raised, because there is not transition between 'active' and 'active',
* We also created a user, with initial state 'new' and triggered a transition: `user.activate()`, after which the user had the new state 'active'.
* trigger functions like `User.activate()` and `User.block()` are auto-generated during state machine construction, 
* Similarly, now the user has state 'active', we could call `user.block()` and after `user.unblock()`, but only in that order,
However, a user needs to have a password to be 'active'. Lets use `activate` to set the password of the user (leaving out the `__init__` method, it will stay the same for now):

```python
from states import StatefulObject, state_machine, states, transition

class User(StatefulObject):
    state = state_machine(
        states=states('new', 'active', 'blocked'),
        transitions=[
            transition('new', 'active', trigger='activate'),
            transition('active', 'blocked', trigger='block'),
            transition('blocked', 'active', trigger='unblock'),
        ]   
    )
    ...
    @state.on_entry('active')
    def set_password(self, password):
        self.password = password

user = User('rosemary')
user.activate(password='very_secret')

assert user.state == 'active'
assert user.password == 'very_secret'
```

* The decorator `@state.on_entry('active')` basically sets `set_password` to be called on entry of the state `active` by the user.
* Remember that to go to the state 'active' the trigger function`user.activate(...)` needed to be called:
    * All arguments passed to the trigger function will be passed to ALL callbacks that are called as a result,
    * Tip: use keyword arguments in callbacks and when calling trigger functions in other than trivial cases. 
* We can similarly set callbacks for `on_exit`, `on_stay`.

To make the possibilities of callbacks clearer, let us add some more:

```python
from states import StatefulObject, state_machine, states, transition

class User(StatefulObject):
    state = state_machine(
        states=states('new', 'active', 'blocked'),
        transitions=[
            transition('new', 'active', trigger='activate'),
            transition('active', 'blocked', trigger='block'),
            transition('blocked', 'active', trigger='unblock'),
        ]   
    )
    ...
    @state.on_entry('active')
    def set_password(self, password):
        self.password = password

    @state.on_entry('*')  # on_entry of all states
    def print_transition(self, **ignored):
        print(f"user {self.username} went to state {self.state}")
    
    @state.on_exit('active')  # called when exiting the 'active' state
    def forget_password(self, **ignored):
        self.password = None

    @state.on_transfer('active', 'blocked')
    def do_something(self, **ignored):
        pass

```
* A wildcard '*' can be used to indicate all states,
* If an action is required on a specific transition, this can be achieved with  `@state.on_transfer(old_state, new_state)`; if too many `on_transfer` callbacks are required on a state machine, there might be a problem in the state definitions, 

To make this state machine a bit more useful, let us include a basic login process. To do this we will add 2 sub-states to the 'active' state:

```python
from states import StatefulObject, state_machine, states, transition, state

class User(StatefulObject):
    state = state_machine(
        states=states('new', 'blocked',
                      active=state(states=states('logged_out', 'logged_in'))),
        transitions=[
            transition('new', 'active', trigger='activate'),
            transition('active', 'blocked', trigger='block'),
            transition('blocked', 'active', trigger='unblock'),
        ]   
    )
    ...
    @state.on_entry('active')
    def set_password(self, password):
        self.password = password

```
*  Notice `active=state(states=states('logged_out', 'logged_in'))`:
    * the sub_state has the same configuration as the main state machine, 
    * but instead of `state_machine` we will use the function `state` returning a dict,
    * actual construction of the sub-states is left to the main `state_machine`
* the transition `transition('new', 'active', trigger='activate')` will now put the user in the 'active.logged_out' state (because it is first in the list of arguments)
* the transition `transition('active', 'blocked', trigger='block')` will put the user in the 'blocked' state independent of the 'active' sub-state the user was in,

Of course the user needs to be able to login and logout and to login, a password must be checked:

```python
from states import StatefulObject, state_machine, states, transition, state

class User(StatefulObject):
    state = state_machine(
        states=states(
            new=state(),  # default: exactly the same result as using just the state name
            blocked=state(),
            active=state(
                states=states('logged_out', 'logged_in'),
                transitions=[
                    transition('logged_out', 'logged_in', trigger='log_in'),
                    transition('logged_in', 'logged_out', trigger='log_out')
                ]
            )
        ),
        transitions=[
            transition('new', 'active', trigger='activate'),
            transition('active', 'blocked', trigger='block'),
            transition('blocked', 'active', trigger='unblock'),
        ]   
    )
    ...
    @state.on_entry('active')
    def set_password(self, password):
        self.password = password

    @state.condition('active.logged_out', 
                     'active.logged_in')
    def verify_password(self, password):
        return self.password == password

    @state.on_entry('active.logged_in')
    def print_welcome(self, **ignored):
        print(f"Welcome back {self.username}")

    @state.on_exit('active.logged_in')
    def print_goodbye(self, **ignored):
        print(f"Goodbye {self.username}")

    @state.on_transfer('active.logged_out', 
                       'active.logged_out')  # this transition was auto-generated by setting a condition on logged_out to logged_in
    def print_welcome(self, **ignored):
        print(f"Sorry, {self.username}, you gave an incorrect password")


user = User('rosemary').activate(password='very_secret').log_in(password='very_secret')
assert user.state == 'active.logged_in'

user = User('rosemary').activate(password='very_secret').log_in(password='not_very_secret')
assert user.state == 'active.logged_out'
```

* With `@state.condition(...)` a conditional transition is introduced:
    * this means that the transition only takes place when the decorated method returns `True`,
    * So, what if the condition returns `False`: 
        - when the condition was added to the state machine, a transition back to the original state was auto-generated,
        - this transition is executed when the conditions fails,
        - in `@state.on_transfer(...)` you can see that it is actually possible to set a callback on this transition,
* Note that the triggers can be chained `User(...).activate(...).log_in(...)`, the trigger functions return the object itself.
    
* This completes a basic state machine for the user flow for application access, it might seem little code, but it accomplished quite a lot:
    * The user must provide a password to become active,
    * the user must be active to be able to log in,
    * the user must provide the correct password to login,
    * the user can be provided with different feedback for each occasion, 
    * the user can be blocked and unblocked and he/she cannot login when blocked,

Lets extend the example one more time:
* We want to block to user after 5 failed login attempts (because 3 is soo limiting ;-)
* Let's add a 'deleted' state for users you want to get rid of (but never throw away data),
* We'll leave out the messages, to keep focus on the task at hand.

```python
from states import StatefulObject, state_machine, states, transition, state

class User(StatefulObject):
    state = state_machine(
        states=states(
            new=state(),  # default: exactly the same result as using just the state name
            blocked=state(),
            active=state(
                states=states('logged_out', 'logged_in'),
                transitions=[
                    transition('logged_out', 'logged_in', trigger='log_in'),
                    transition('logged_in', 'logged_out', trigger='log_out')
                 ]
            ),
            deleted=state(),
        ),
        transitions=[
            transition('new', 'active', trigger='activate'),
            transition('active', 'blocked', trigger='block'),
            transition('blocked', 'active', trigger='unblock'),
            transition('*', 'deleted', trigger='delete'),
        ]   
    )

    def __init__(self, username, max_logins=5):
        super().__init__(state='new')
        self.username = username
        self.password = None
        self.max_logins = max_logins
        self.login_count = 0

    @state.on_entry('active')
    def set_password(self, password):
        self.password = password

    @state.condition('active.logged_out', 
                     'active.logged_in')
    def verify_password(self, password):
        return self.password == password

    @state.condition('active.logged_out', 
                     'blocked')
    def check_login_count(self, **ignored):
        return self.login_count > self.max_logins

    @state.on_transfer('active.logged_out', 
                       'active.logged_out')  # this transition was auto-generated by setting a condition on logged_out to logged_in
    def inc_login_count(self, **ignored):
        self.login_count += 1

    @state.on_exit('blocked')
    @state.on_entry('active.logged_in')
    def reset_login_count(self, **ignored):
        self.login_count = 0


user = User('rosemary').activate(password='very_secret')

for _ in range(user.max_logins):
    user.login('also_very_secret')
    assert user.state == 'active.logged_out'

user.login('also_very_secret')  # the 6th time
assert user.state == 'blocked'

```

 
---

## Change Log
This is a new section of the readme, starting at version 0.4.0.

####Version 0.5.0
A major overhaul, with many improvements, especially in configuration and performance:
**Features**
- simplified configuration and partial auto-generation of state-machine (minimally just using state names),
- adding callbacks to the state machine using decorators, instead of directly in the main configuration,
- better validation with improved error messages,
- Corrected and improved README.md (this document).

**Changes**
- configuration now uses validating functions instead of plain dicts and lists and they require less typing. 

**Bug fixes**
- none.


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
 
## Rules (for the mathematically minded)
The state machine in the module has the following rules for setting up states and transitions:

* notation:
    * (A, B, C)  : states of a state managed object (called 'object' from now)
    * (A(B, C)) : state A with nested states B, C,
    * A.B : sub-state B of A; A.B is called a state path,
    * <A, B>   : transition between state A and state B
    * <A, B or C>: transition from A to B or C, depending on condition functions,
    * <*, B>: shorthand for all transitions to state B,
* allowed transitions, given states A,  B, C(E, F) and D(G, H):
    * <A, B>: basic transition, configured as {"old_state": "A", "new_state": "B"}
    * <A, A>: transition from a state to itself
    * <C.E, A>: transition from a specific sub-state of C to A
    * <C, D.G>: transition from any sub-state of C to specific state D.G
    * <A, C>: transition from A to C.E, E being the initial state of C because it was explicitly set or because it is the first state in E
    * <C.F, D.H>: transitioning from one sub-state in a state to another sub-state in another state. Note that this would call (if present) on_exit on F and C and on_entry on D and H in that order.
* adding conditional transitions, given transition <A, B or C or D>:
    * <A, B> and <A, C> must have conditions attached, these condition will be checked in order of configuration; 
    * D does not need to have a condition attached meaning it will always be the next state if the conditions on <A, B> and <A, C> fail,
    * (If <A, D> does have a condition attached, a default state transition <A, A> will be created during state machine construction),
* an object cannot just be in state A if A has substates: given state A(B, C), the object can be in A.B or A.C, not in A

## Authors

Lars van Gemerden (rational-it) - initial code and documentation.

## License

See LICENSE.txt.



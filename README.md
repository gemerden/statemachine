# statemachine
Easy to use state machine to manage the state of python objects

## intro
This state machine implementation is developed with the following goals:

* Easy to use API
* Usable for any (almost, I'm sure) python class with a finite number of states
* Readable, straightforward, easy-to-adapt code
* One state machine instance can manage the state of many objects
* Reasonably fast

## concepts
The following concepts are used

* State: some condition of an object; objects can be in one state at the time
* Transition: transition of the object from one state to another resulting in a number of callbacks
* Trigger: method called on an object that results in a state change (can have condition)
* State machine: class that manages the states of objects according to predefined states and transitions
* Callback: function called on transitions by the state machine,
* Condition: condition for a specific state transition to take place, this is checked before any (other) callbacks
* Switching: by using multiple conditional transitions from the same state with the same trigger, the next state can be determined by e.g. the attributes of the object

## features
The module has the following basic and some more advanced features:

* trigger state transitions by setting trigger name in machine configuration:
    * same trigger can be set for different transitions,
    * trigger method can pass arguments to callbacks,
* conditions (callbacks) can be set on transitions to take place:
    * if a transition is triggered, but the condition is not met, the transition does not take place
* switched transitions can be used to go from one state to another depending on conditions
    * trigger can be used for conditional (switched) transition,
    * to do this, create multiple trasnitions from the same state to different states and give them different conditions
* state transitions can be started by explicitly setting the state (obj.state = "some_state"):
    * if a condition is set and not met on the transition an exception is raised, because the callbacks would not be called,
    * if the callbacks function require extra arguments (apart from the state managed object), this method will fail bacause it cannot pass arguments
* a number of callbacks can be installed for each state and transition, in order:
    * StateMachine.before_any_exit(self, obj. **args, ***kwargs),
    * State.on_exit(self, obj. **args, ***kwargs),
    * Transition.on_transfer(self, obj. **args, ***kwargs), # after this the state is changed on the object
    * State.on_entry(self, obj. **args, ***kwargs),
    * StateMachine.after_any_entry(self, obj. **args, ***kwargs)
        * with: obj the state managed object
        * with: **args, ***kwargs the arguments passed to the trigger (signature of callbacks must match how the trigger is called)
    * note that if a condition is present and not met, none of these functions are called
* callbacks can be methods on the class of which the state is managed by the machine:
    * This is the case when the calback is configured as a string (e.g. "on_entry": "do_callback"),
* wildcards and listed states can be used to define multiple transitions at once:
    * e.g. transition {"old_state": "*", "new_state": ["A", "B"]} would create transitions from all states to both state A and B
* custom exceptions:
    * MachineError: raised in case of a misconfiguration of the state machine,
    * TransitionError: raised in case of e.g. an attempt to trigger a non-existing transition,
    * SetStateError: raised when obj.state = "some_state" fails


## basic usage example
Lets start with an example:
``` python   
    def printline(obj, old_state, new_state):  # simple callback function
        print "---"
    
    # somewhat more verbose callback function
    def printer(obj, old_state, new_state):
        print "transition <%s, %s> on %s" % ( old_state, new_state, str(obj))
    
    # inherit from BaseStateObject to let it store state and be able to call triggers
    class Matter(BaseStateObject):  
        
        # instantiate the state machine that will handle all instances of Matter
        machine = StateMachine(  
            name="matter machine",  # give it a name
            states=[  # state configuration
                {"name": "solid", "on_entry":[printer], "on_exit":[printer]},
                {"name": "liquid", "on_entry": [printer], "on_exit": [printer]},
                {"name": "gas", "on_entry": [printer], "on_exit": [printer]}
            ],
            transitions=[  # transition configuration
                {"old_state": "solid", "new_state": "liquid", "triggers": "melt", "on_transfer": [printer]},
                {"old_state": "liquid", "new_state": "gas", "triggers": "evaporate", "on_transfer": [printer]},
                {"old_state": "gas", "new_state": "liquid", "triggers": "condense", "on_transfer": [printer]},
                {"old_state": "liquid", "new_state": "solid", "triggers": "freeze", "on_transfer": [printer]}
            ],
        )
        
        # give the object a name for printing purposes
        def __init__(self, name):
            super(Matter, self).__init__(initial="solid")  # initial state is "solid"
            self.name = name

        def __str__(self):
            return self.name + "(%s)" % self.state
    
    
    # so far for using the API, now lets see what we have:
    
    block = Matter("block")  # instantiate an object

    # now call the trigger functions to cause a state change
    block.melt()  # the state is now 'liquid'
    block.evaporate()
    block.condense()
    block.freeze()  # the state is now 'solid' again
    try:
        block.evaporate()  # you cannot evaporate a 'solid' (here)
    except TransitionError as e:
        print "Oh oh: error intercepted: " + e.message

    # you can also change the state by setting it
    block.state = "liquid"
    block.state = "gas"
    block.state = "liquid"
    block.state = "solid"
    try:
        block.state = "gas"  # 'solid' can still not be evaporated
    except TransitionError as e:
        print ">>> Oh oh: error intercepted: " + e.message
```

 Notes:

  * More documentation and usage samples can be found in the code comments and the tests
  * Argument 'condition' (not shown) of a transition can be used to block a transition
  * All callbacks have the signature func(obj, old_state, new_state), with old_state and new_state as strings (str)
  * 'condition' and all callbacks are configured in the constructor of the state machine (on_entry=.., on_transfer=..),
  * All callbacks are optional, if no callback is given a no-action callback is used.
  * Conditions return a bool to indicate whether the transition took place (only relevant when a condition is set on the transition)
  * Callbacks can be initiated with a single function or a list of functions, apart from 'condition'
  * Wildcards "*" or lists of state names can be used for old_state or new_state in transition configuration so that all transitions to or from that state are created.



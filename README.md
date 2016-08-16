# statemachine
Easy to use state machine to manage the state of python objects

## intro
This state machine implementation is developed with the following goals:

* Easy to use API
* Usable for any (almost, I'm sure) python class with a finite number of states
* Readable, straightforward, easy-to-adapt code
* One state machine instance can manage the state of many objects
* Reasonably fast

## general
The following concepts are used

* State: some condition of an object; objects can be in one state at the time
* Transition: transition of the object from one state to another resulting in a number of callbacks
* Trigger: method called on an object that results in a state change (can have condition)
* State machine: class that manages the states of objects according to predefined states and transitions
* Callback: function (func(obj, old_state, new_state)) called on transitions by the state machine, in order:
    * StateMachine.before_any_exit,
    * State.on_exit,
    * Transition.on_transfer, # after this the state is changed on the object
    * State.on_entry,
    * StateMachine.after_any_entry
* Condition: condition for a specific state transition to take place, this is checked before any (other) callbacks

The exact execution of callbacks and conditions can be seen in the Transition.execute method.

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

  * Argument 'condition' (not shown) of a transition can be used to block a transition
  * All callbacks have the signature func(obj, old_state, new_state), with old_state and new_state as strings (str)
  * 'condition' and all callbacks are configured in the constructor of the state machine (on_entry=.., on_transfer=..),
  * callbacks can be initiated with a single function or a list of functions, apart from 'condition'
  * All callbacks are optional, if no callback is given a no-action callback is used.


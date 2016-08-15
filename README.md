# statemachine
Easy to use state machine to manage the state of python objects

## intro
This state machine implementation is developed with the following goals:

* Easy to use API
* Usable for any (almost, I'm sure) python class with a finite number of states
* Readable, straightforward, easy-to-adapt code
* One state machine instance can manage state of many objects
* Reasonably fast


## basic usage
Lets start with an example:

`
    
    def printline(obj):  # simple callback function
        print "---"
    
    # somewhat more verbose callback function
    def printer(obj):  
        print "called 'printer' for '%s'" % str(obj)
    
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
    
    # instantiate
    block = Matter("block")

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

`


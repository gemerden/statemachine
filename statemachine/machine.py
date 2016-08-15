from functools import partial


def listify(list_or_item):
    """utitity function to ensure an argument becomes a list if it is not one yet"""
    try:
        return list(list_or_item)
    except TypeError:
        return [list_or_item]


class MachineError(ValueError):
    """Exception indicating an error in the construction of the state machine"""
    pass


class TransitionError(ValueError):
    """Exception indicating an error in the in a state transition of an object"""
    pass


class State(object):
    """class for the internal representation of state in the state machine"""
    def __init__(self, machine, name, on_entry=(), on_exit=()):
        self.machine = machine
        self.name = name
        self._on_entry = listify(on_entry)
        self._on_exit = listify(on_exit)

    def on_entry(self, obj):
        for callback in self._on_entry:
            callback(obj)

    def on_exit(self, obj):
        for callback in self._on_exit:
            callback(obj)


class Transition(object):
    """class for the internal representation of transitions in the state machine"""
    def __init__(self, machine, old_state, new_state, on_transfer=(), condition=lambda obj: True):
        self.machine = machine
        self.old_state = old_state
        self.new_state = new_state
        self._on_transfer = listify(on_transfer)
        self.condition = condition

    def on_transfer(self, obj):
        for callback in self._on_transfer:
            callback(obj)

    def execute(self, obj):
        """
        Method calling all the callbacks of a state transition ans changing the actual object state (if condition
        returns True).
        :param obj: object of which the stae is managed
        """
        if self.condition(obj):
            self.machine.before_any_exit(obj)
            self.old_state.on_exit(obj)
            self.on_transfer(obj)
            obj._change_state(self.new_state.name)
            self.new_state.on_entry(obj)
            self.machine.after_any_entry(obj)

    def __str__(self):
        """string representing the transition"""
        return "<%s, %s>" %(self.old_state.name, self.new_state.name)


class StateMachine(object):

    state_class = State  # class used for the internal representation of state
    transition_class = Transition  # class used for the internal representation of transitions

    def __init__(self, name, states, transitions, before_any_exit=(), after_any_entry=()):
        """
        Constructor of the state machine, used to define all properties of the machine.
        :param name: the name of the machine
        :param states: a list of state properties:
        {
            "name": "solid",  # the state name
            "on_entry":[some_method],  # callback function(obj) called when an objects enter the state (single or list)
            "on_exit":[some_method]  # callback function(obj) called when an objects exits the state (single or list)
        }
        :param transitions: a list of transition properties:
        {
            "old_state": "solid",  # the name of the 'from' state of the transition
            "new_state": "liquid",  # the name of the 'to' state of the transition
            "triggers": ["melt", "heat"],  # name of the triggers triggering the transition: e.g. obj.heat()
            "on_transfer": [printer],# callback function(obj) called when an objects transfers from state to
                state(single or list)
            "condition": function(obj); called to determine whether a transtion will actually take place (return
                True to cause state change)
        }
        :param before_any_exit: callback function(obj) called before an objects exits any state (single or list)
        :param after_any_entry: callback function(obj) called after an objects enters any state (single or list)
        """
        self.name = name
        self.states = self._create_states(states)
        self.transitions = self._create_transitions(transitions)
        self.triggers = self._create_trigger_dict(transitions)
        self._before_any_exit = listify(before_any_exit)
        self._after_any_entry = listify(after_any_entry)

    def _create_states(self, states):
        """creates a dictionary of state_name: State key value pairs"""
        state_dict = {}
        for state in states:
            if state["name"] in state_dict:
                raise MachineError("two states with the same name in state machine")
            state_dict[state["name"]] = self.state_class(machine=self, **state)
        return state_dict

    def _create_transitions(self, transitions):
        """creates a dictionary of (old state name, new state name): Transition key value pairs"""
        transition_dict = {}
        for trans in transitions:
            if (trans["old_state"], trans["new_state"]) in transition_dict:
                raise MachineError("two transitions between same states in state machine")
            transition = self.transition_class(machine=self,
                                               old_state=self.states[trans["old_state"]],
                                               new_state=self.states[trans["new_state"]],
                                               on_transfer=trans.get("on_transfer", ()),
                                               condition=trans.get("condition", lambda obj: True))
            transition_dict[(trans["old_state"], trans["new_state"])] = transition
        return transition_dict

    def _create_trigger_dict(self, transitions):
        """creates a dictionary of (old state name, trigger name): Transition key value pairs"""
        trigger_dict = {}
        for trans in transitions:
            for trigger_name in trans.get("triggers", ()):
                key = (trans["old_state"], trigger_name)
                if key in trigger_dict:
                    raise MachineError("same trigger for same start state and different transitions")
                trigger_dict[key] = self.transitions[(trans["old_state"], trans["new_state"])]
        return trigger_dict

    def before_any_exit(self, obj):
        """called before any transition"""
        for callback in self._before_any_exit:
            callback(obj)

    def after_any_entry(self, obj):
        """called after any transitions"""
        for callback in self._after_any_entry:
            callback(obj)

    def do_trigger(self, trigger, obj):
        """executes the transition when called through a trigger"""
        try:
            self.triggers[(obj.state, trigger)].execute(obj)
        except KeyError:
            raise TransitionError("trigger '%s' does not exist for state '%s'" % (trigger, obj.state))

    def set_state(self, state, obj):
        """executes the transition when called by setting the state: objects.state = "some_state"""
        try:
            self.transitions[(obj.state, state)].execute(obj)
        except KeyError:
            raise TransitionError("transition <%s, %s> does not exist" % (obj.state, state))


class BaseStateObject(object):
    """
    Base class for objects with a state machine managed state. State can change by calling triggers as defined in
    transitions or by setting the 'state' property.
    """

    def __init__(self, initial, *args, **kwargs):
        """
        Constructor for the base class
        :param initial: string indicating the initial state of the object
        :param args: any arguments to be passed to super constructor in case of inheritance
        :param kwargs: any keyword arguments to be passed to super constructor in case of inheritance
        """
        super(BaseStateObject, self).__init__(*args, **kwargs)
        assert initial in self.machine.states
        self._new_state = initial
        self._old_state = None

    def __getattr__(self, trigger):
        """
        Allows calling the triggers to cause a transition
        :param trigger: name of the trigger
        :return: partial function that allows the trigger to be called like object.some_trigger()
        """
        return partial(self.machine.do_trigger, trigger=trigger, obj=self)

    def _change_state(self, state):  # override if old_state is stored e.g. in a state history
        """
        called by the state machine to actually change the state durint the exceution of callbacks
        :param state: the new state name
        """
        self._old_state = self._new_state
        self._new_state = state

    def get_state(self):
        """
        :return: the current state
        """
        return self._new_state

    def set_state(self, state):
        """
        Causes the state machine to call all releveat callbacks and change the state of the object
        :param state: the new state name
        """
        if state == self._new_state:
            return
        self.machine.set_state(state, self)

    state = property(get_state, set_state)  # turn state into a property


if __name__ == "__main__":
    """
    Small usage example
    """

    def printline(obj):
        print "---"

    def printer(obj):
        print "called 'printer' for '%s'" % str(obj)

    class Matter(BaseStateObject):

        machine = StateMachine(
            name="matter machine",
            states=[
                {"name": "solid", "on_entry":[printer], "on_exit":[printer]},
                {"name": "liquid", "on_entry": [printer], "on_exit": [printer]},
                {"name": "gas", "on_entry": [printer], "on_exit": [printer]}
            ],
            transitions=[
                {"old_state": "solid", "new_state": "liquid", "triggers": ["melt", "heat"], "on_transfer": [printer]},
                {"old_state": "liquid", "new_state": "gas", "triggers": ["evaporate", "heat"], "on_transfer": [printer]},
                {"old_state": "gas", "new_state": "liquid", "triggers": ["condense", "cool"], "on_transfer": [printer]},
                {"old_state": "liquid", "new_state": "solid", "triggers": ["freeze", "cool"], "on_transfer": [printer]}
            ],
            after_any_entry=printline
        )

        def __init__(self, name):
            super(Matter, self).__init__(initial="solid")
            self.name = name

        def __str__(self):
            return self.name + "(%s)" % self.state

    lumpy = Matter("lumpy")

    lumpy.melt()
    lumpy.evaporate()
    lumpy.condense()
    lumpy.freeze()
    try:
        lumpy.evaporate()
    except TransitionError as e:
        print ">>> JEEP: error intercepted: " + e.message

    lumpy.heat()
    lumpy.heat()
    lumpy.cool()
    lumpy.cool()
    try:
        lumpy.cool()
    except TransitionError as e:
        print ">>> JEEP: error intercepted: " + e.message

    lumpy.state = "liquid"
    lumpy.state = "gas"
    lumpy.state = "liquid"
    lumpy.state = "solid"
    try:
        lumpy.state = "gas"
    except TransitionError as e:
        print ">>> JEEP: error intercepted: " + e.message



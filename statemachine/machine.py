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

    def on_entry(self, obj, old_state, new_state):
        for callback in self._on_entry:
            callback(obj, old_state, new_state)

    def on_exit(self, obj, old_state, new_state):
        for callback in self._on_exit:
            callback(obj, old_state, new_state)


class Transition(object):
    """class for the internal representation of transitions in the state machine"""
    def __init__(self, machine, old_state, new_state, on_transfer=(), condition=lambda obj, o, n: True):
        self.machine = machine
        self.old_state = old_state
        self.new_state = new_state
        self._on_transfer = listify(on_transfer)
        self.condition = condition

    def on_transfer(self, obj, old_state, new_state):
        for callback in self._on_transfer:
            callback(obj, old_state, new_state)

    def execute(self, obj):
        """
        Method calling all the callbacks of a state transition ans changing the actual object state (if condition
        returns True).
        :param obj: object of which the state is managed
        """
        old_state = self.old_state.name
        new_state = self.new_state.name
        if self.condition(obj, old_state, new_state):
            self.machine.before_any_exit(obj, old_state, new_state)
            self.old_state.on_exit(obj, old_state, new_state)
            self.on_transfer(obj, old_state, new_state)
            obj._change_state(new_state)
            self.new_state.on_entry(obj, old_state, new_state)
            self.machine.after_any_entry(obj, old_state, new_state)

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
            "on_entry":[some_method],  # callback function called when an objects enter the state (single or list)
            "on_exit":[some_method]  # callback function called when an objects exits the state (single or list)
        }
        :param transitions: a list of transition properties:
        {
            "old_state": "solid",  # the name of the 'from' state of the transition
            "new_state": "liquid",  # the name of the 'to' state of the transition
            "triggers": ["melt", "heat"],  # name of the triggers triggering the transition: e.g. obj.heat()
            "on_transfer": [printer],# callback function called when an objects transfers from state to
                state(single or list)
            "condition": function(obj); called to determine whether a transtion will actually take place (return
                True to cause state change)
        }
        :param before_any_exit: callback function called before an objects exits any state (single or list)
        :param after_any_entry: callback function called after an objects enters any state (single or list)

        Note that all callback functions (including 'condition') have the signature:
            func(obj, old_state, new_state), with old_state and new_state as strings
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
            try:
                transition = self.transition_class(machine=self,
                                                   old_state=self.states[trans["old_state"]],
                                                   new_state=self.states[trans["new_state"]],
                                                   on_transfer=trans.get("on_transfer", ()),
                                                   condition=trans.get("condition", lambda obj, o, n: True))
                transition_dict[(trans["old_state"], trans["new_state"])] = transition
            except KeyError:
                raise MachineError("non-existing state when constructing transitions")
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

    def before_any_exit(self, obj, old_state, new_state):
        """called before any transition"""
        for callback in self._before_any_exit:
            callback(obj, old_state, new_state)

    def after_any_entry(self, obj, old_state, new_state):
        """called after any transitions"""
        for callback in self._after_any_entry:
            callback(obj, old_state, new_state)

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
    Small usage example: a minimal state machine (see also the tests)
    """
    def printer(action):
        def func(obj, old_state, new_state):
            print "'%s' for '%s' results in transition <%s, %s>" % (action, str(obj), old_state, new_state)
        return func

    class Switch(BaseStateObject):

        machine = StateMachine(
            name="matter machine",
            states=[
                {"name": "on"},
                {"name": "off"},
            ],
            transitions=[
                {"old_state": "off", "new_state": "on", "triggers": ["turn_on", "switch"], "on_transfer": printer("turn on")},
                {"old_state": "on", "new_state": "off", "triggers": ["turn_off", "switch"], "on_transfer": printer("turn off")},
            ],
        )

        def __init__(self, name, initial="off"):
            super(Switch, self).__init__(initial=initial)
            self.name = name

        def __str__(self):
            return self.name + " (%s)" % self.state

    light_switch = Switch("lights")

    light_switch.turn_on()
    light_switch.turn_off()
    try:
        light_switch.turn_off()
    except TransitionError as e:
        print "error: " + e.message
    print
    light_switch.switch()
    light_switch.switch()
    print
    light_switch.state = "on"
    light_switch.state = "off"
    light_switch.state = "off"  # does not result in any callbacks because the switch is already off



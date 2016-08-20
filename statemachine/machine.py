from collections import OrderedDict
from functools import partial

from statemachine.tools import listify, callbackify

__author__  = "lars van gemerden"


class MachineError(ValueError):
    """Exception indicating an error in the construction of the state machine"""
    pass


class TransitionError(ValueError):
    """Exception indicating an error in the in a state transition of an object"""
    pass


class BaseMachinePart(object):

    def __init__(self, machine, *args, **kwargs):
        super(BaseMachinePart, self).__init__(*args, **kwargs)
        self.machine = machine



class State(object):
    """class for the internal representation of state in the state machine"""
    def __init__(self, machine, name, on_entry=(), on_exit=()):
        self.machine = machine
        self.name = name
        self.on_entry = callbackify(on_entry)
        self.on_exit = callbackify(on_exit)


class Transition(object):
    """class for the internal representation of transitions in the state machine"""
    def __init__(self, machine, old_state, new_state, on_transfer=(), condition=lambda obj, o, n: True):
        self.machine = machine
        self.old_state = old_state
        self.new_state = new_state
        self.on_transfer = callbackify(on_transfer)
        self.condition = callbackify(condition)

    def execute(self, obj, *args, **kwargs):
        """
        Method calling all the callbacks of a state transition ans changing the actual object state (if condition
        returns True).
        :param obj: object of which the state is managed
        :param args: arguments of the callback
        :param kwargs: keyword arguments of the callback
        :return: bool, whether the transition took place
        """
        if self.condition(obj):
            self.machine.before_any_exit(obj, *args, **kwargs)
            self.old_state.on_exit(obj, *args, **kwargs)
            self.on_transfer(obj, *args, **kwargs)
            obj._change_state(self.new_state.name)
            self.new_state.on_entry(obj, *args, **kwargs)
            self.machine.after_any_entry(obj, *args, **kwargs)
            return True
        return False

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
        self.before_any_exit = callbackify(before_any_exit)
        self.after_any_entry = callbackify(after_any_entry)

    def _create_states(self, states):
        """creates a dictionary of state_name: State key value pairs"""
        state_dict = OrderedDict()
        for state in states:
            if state["name"] in state_dict:
                raise MachineError("two states with the same name in state machine")
            state_dict[state["name"]] = self.state_class(machine=self, **state)
        return state_dict

    def _create_transitions(self, transitions):
        """creates a dictionary of (old state name, new state name): Transition key value pairs"""
        transition_dict = {}
        transitions = self._expand_transitions(transitions)
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

    def _expand_transitions(self, transitions):
        """replaces transitions with '*' wildcards and list of states with multiple one-to-one transitions"""
        current = [(t["old_state"], t["new_state"]) for t in transitions]
        for trans in transitions[:]:
            if trans["old_state"] == "*" or isinstance(trans["old_state"], (list, tuple)):
                old_state_names = self.states.keys() if trans["old_state"] == "*" else trans["old_state"]
                for state_name in old_state_names:
                    if state_name != trans["new_state"] and (state_name, trans["new_state"]) not in current:
                        new_trans = trans.copy()
                        new_trans["old_state"] = state_name
                        transitions.append(new_trans)
                transitions.remove(trans)
        current = [(t["old_state"], t["new_state"]) for t in transitions]
        for trans in transitions[:]:
            if trans["new_state"] == "*" or isinstance(trans["new_state"], (list, tuple)):
                new_state_names = self.states.keys() if trans["new_state"] == "*" else trans["new_state"]
                for state_name in new_state_names:
                    if state_name != trans["old_state"] and (trans["old_state"], state_name) not in current:
                        new_trans = trans.copy()
                        new_trans["new_state"] = state_name
                        transitions.append(new_trans)
                transitions.remove(trans)
        return transitions

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

    def do_trigger(self, trigger, obj):
        """executes the transition when called through a trigger"""
        try:
            return self.triggers[(obj.state, trigger)].execute(obj)
        except KeyError:
            raise TransitionError("trigger '%s' does not exist for state '%s'" % (trigger, obj.state))

    def set_state(self, state, obj):
        """executes the transition when called by setting the state: obj.state = 'some_state' """
        try:
            self.transitions[(obj.state, state)].execute(obj)
        except KeyError:
            raise TransitionError("transition <%s, %s> does not exist" % (obj.state, state))


class BaseStateObject(object):
    """
    Base class for objects with a state machine managed state. State can change by calling triggers as defined in
    transitions or by setting the 'state' property.
    """

    def __init__(self, initial=None, *args, **kwargs):
        """
        Constructor for the base class
        :param initial: string indicating the initial state of the object; if None, take first state of machine
        :param args: any arguments to be passed to super constructor in case of inheritance
        :param kwargs: any keyword arguments to be passed to super constructor in case of inheritance
        """
        super(BaseStateObject, self).__init__(*args, **kwargs)
        if not initial:
            self._new_state = self.machine.states.keys()[0]
        elif initial not in self.machine.states:
            raise ValueError("initial state does not exist")
        self._new_state = initial
        self._old_state = None

    def __getattr__(self, trigger):
        """
        Allows calling the triggers to cause a transition; the triggers return a bool indicating whether the
            transition took place.
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

    print "returning True: ", light_switch.turn_on()
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



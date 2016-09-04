from collections import OrderedDict
from functools import partial

from statemachine.tools import listify, callbackify, Path

__author__  = "lars van gemerden"


class MachineError(ValueError):
    """Exception indicating an error in the construction of the state machine"""
    pass


class TransitionError(ValueError):
    """Exception indicating an error in the in a state transition of an object"""
    pass


class SetStateError(ValueError):
    """Exception indicating that explicitly setting the state of an object failed"""
    pass


class Transition(object):
    """class for the internal representation of transitions in the state machine"""
    def __init__(self, machine, old_state, new_state, on_transfer=(), condition=None, **kwargs):
        self.machine = machine
        self._validate_states(old_state, new_state)
        self.old_path = Path(old_state)
        self.new_path = Path(new_state)
        self.old_states = list(self.old_path.iter_out(self.machine))
        self.new_states = list(self.new_path.iter_in(self.machine))
        self.on_transfer = callbackify(on_transfer)
        self.condition = callbackify(condition) if condition else None

    def _validate_states(self, old_state, new_state):
        """ assures that no internal transitions are defined on an outer state level"""
        old_states = old_state.split(".", 1)
        new_states = new_state.split(".", 1)
        if (len(old_states) > 1 or len(new_states) > 1) and old_states[0] == new_states[0]:
            raise MachineError("inner transitions in a nested machine cannot be defined at the outer machine level")

    def exit_states(self, obj, *args, **kwargs):
        """ calls all exit methods for states being exited as a result of a transition"""
        old_state = self.old_states[0]
        for state in obj.state_path.tail(old_state.path).iter_out(old_state):
            state.exit(obj, *args, **kwargs)
        for state in self.old_states:
            state.exit(obj, *args, **kwargs)

    def enter_states(self, obj, *args, **kwargs):
        """ calls all enter methods for states being entered as a result of a transition"""
        for state in self.new_states:
            state.enter(obj, *args, **kwargs)
        for state in self.new_states[-1].iter_initial():
            state.enter(obj, *args, **kwargs)

    def execute(self, obj, *args, **kwargs):
        """
        Method calling all the callbacks of a state transition ans changing the actual object state (if condition
        returns True).
        :param obj: object of which the state is managed
        :param args: arguments of the callback
        :param kwargs: keyword arguments of the callback
        :return: bool, whether the transition took place
        """
        if not self.condition or self.condition(obj):
            obj.store_state()
            self.machine.before_any_exit(obj, *args, **kwargs)
            self.exit_states(obj, *args, **kwargs)
            self.on_transfer(obj, *args, **kwargs)
            self.enter_states(obj, *args, **kwargs)
            self.machine.after_any_entry(obj, *args, **kwargs)
            return True
        return False

    def __str__(self):
        """string representing the transition"""
        return "<%s, %s>" %(str(self.old_path), str(self.new_path))


class BaseState(object):
    """base class for the both ChildState and ParentState"""
    def __init__(self, name, *args, **kwargs):
        """
        Constructor of BaseState:

        :param name: name of the state, must be unique within the parent state machine
        """
        super(BaseState, self).__init__(*args, **kwargs)
        self.name = name


class ChildState(BaseState):
    """class for the internal representation of a state without substates in the state machine"""

    def __init__(self, super_state=None, on_entry=(), on_exit=(), *args, **kwargs):
        """
        Constructor of ChildState:

        :param super_state: state (-machine) that contains this state
        :param on_entry: callback(s) that will be called, when an object enters this state
        :param on_exit: callback(s) that will be called, when an object exits this state
        """
        super(ChildState, self).__init__(*args, **kwargs)
        self.super_state = super_state
        self.on_entry = callbackify(on_entry)
        self.on_exit = callbackify(on_exit)

    @property
    def path(self):
        """ returns the path from the top state machine to this state """
        try:
            return self.__path
        except AttributeError:
            self.__path = Path(reversed([s.name for s in self.iter_up()]))
            return self.__path

    def exit(self, obj, *args, **kwargs):
        """strips the name of this state from the state in the object and calls the on_exit callbacks"""
        self.on_exit(obj, *args, **kwargs)
        obj._new_state = obj._new_state[:-1]

    def enter(self, obj, *args, **kwargs):
        """adds the name of this state to the state in the object and calls the on_entry callbacks"""
        obj._new_state = obj._new_state + self.name
        self.on_entry(obj, *args, **kwargs)

    def iter_up(self):
        """iterates over all states from this state to the top containing state"""
        state = self
        while state.super_state is not None:
            yield state
            state = state.super_state

    def __str__(self):
        return str(self.path)


class ParentState(BaseState):
    """ class representing and handling the substates of a state"""

    transition_class = Transition  # class used for the internal representation of transitions

    def __init__(self, states=(), transitions=(), initial=None, before_any_exit=(), after_any_entry=(), *args, **kwargs):
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
        :param initial: optional name of the initial state
        :param before_any_exit: callback function called before an objects exits any state (single or list)
        :param after_any_entry: callback function called after an objects enters any state (single or list)

        Note that all callback functions (including 'condition') have the signature:
            func(obj, *args, **kwargs); triggers can pass the args and kwargs
        """
        super(ParentState, self).__init__(*args, **kwargs)
        self.sub_states = self._create_states(states)
        self.transitions = self._create_transitions(transitions)
        self.triggering = self._create_triggering(transitions)
        self.initial = self._get_initial(initial)
        self.before_any_exit = callbackify(before_any_exit)
        self.after_any_entry = callbackify(after_any_entry)
        self.triggers = self._get_triggers()

    def _get_initial(self, initial):
        """ returns the nested inital state"""
        if initial:
            try:
                initial_state = self.sub_states[initial]
                while len(initial_state):
                    initial_state = initial_state.initial
                return initial_state
            except KeyError:
                raise MachineError("initial state '%s' does not exist" % initial)

    def _get_triggers(self):
        """ gets a set of all trigger names in the state amchine and all sub states recursively """
        triggers = set(t[1] for t in self.triggering)
        for state in self:
            triggers.update(state.triggers)
        return triggers

    def _create_states(self, states):
        """creates a dictionary of state_name: BaseState key value pairs"""
        state_dict = OrderedDict()
        for state in states:
            if state["name"] in state_dict:
                raise MachineError("two sub_states with the same name in state machine")
            state_dict[state["name"]] = self.__class__(super_state=self, **state)
        return state_dict

    def _create_transitions(self, transitions):
        """creates a dictionary of (old state name, new state name): Transition key value pairs"""
        transition_dict = {}
        transitions = self._expand_transitions(transitions)
        for trans in transitions:
            old_path, new_path = Path(trans["old_state"]), Path(trans["new_state"])
            if (old_path, new_path) in transition_dict:
                raise MachineError("two transitions between same sub_states in state machine")
            if not (old_path.has_in(self) and new_path.has_in(self)):
                raise MachineError("non-existing state when constructing transitions")
            transition_dict[old_path, new_path] = self.transition_class(machine=self, **trans)
        return transition_dict

    def _expand_transitions(self, transitions):
        """replaces transitions with '*' or list of sub_states with multiple one-to-one transitions"""
        current = [(t["old_state"], t["new_state"]) for t in transitions]
        for trans in transitions[:]:
            if trans["old_state"] == "*" or isinstance(trans["old_state"], (list, tuple)):
                old_state_names = self.sub_states.keys() if trans["old_state"] == "*" else trans["old_state"]
                for state_name in old_state_names:
                    if state_name != trans["new_state"] and (state_name, trans["new_state"]) not in current:
                        new_trans = trans.copy()
                        new_trans["old_state"] = state_name
                        transitions.append(new_trans)
                transitions.remove(trans)
        current = [(t["old_state"], t["new_state"]) for t in transitions]
        for trans in transitions[:]:
            if trans["new_state"] == "*" or isinstance(trans["new_state"], (list, tuple)):
                new_state_names = self.sub_states.keys() if trans["new_state"] == "*" else trans["new_state"]
                for state_name in new_state_names:
                    if state_name != trans["old_state"] and (trans["old_state"], state_name) not in current:
                        new_trans = trans.copy()
                        new_trans["new_state"] = state_name
                        transitions.append(new_trans)
                transitions.remove(trans)
        return transitions

    def _create_triggering(self, transitions):
        """creates a dictionary of (old state name, trigger name): Transition key value pairs"""
        trigger_dict = {}
        for trans in transitions:
            old_path, new_path = Path(trans["old_state"]), Path(trans["new_state"])
            for trigger_name in listify(trans.get("triggers", ())):
                trigger_key = (old_path, trigger_name)
                if trigger_key not in trigger_dict:
                    trigger_dict[trigger_key] = []
                trigger_dict[trigger_key].append(self.transitions[old_path, new_path])
        return self._check_triggering(trigger_dict)

    def _check_triggering(self, trigger_dict):
        for (_, trigger), transitions in trigger_dict.iteritems():
            for i, transition in enumerate(transitions[:-1]):
                if not transition.condition:
                    raise MachineError("unreachable transition %s for trigger %s" % (str(transitions[i+1]), trigger))
        return trigger_dict

    def __len__(self):
        return len(self.sub_states)

    def __contains__(self, key):
        try:
            self[key]
            return True
        except KeyError:
            return False

    def __getitem__(self, key):
        """
        Gets sub states according to string key or transition according to the 2-tuple (e.g.
            key: ("on.washing", "off.broken"))
        """
        if isinstance(key, str):
            return self.sub_states[key]
        elif isinstance(key, tuple) and len(key) == 2:
            return self.transitions[Path(key[0]), Path(key[1])]
        raise KeyError("key is not a string or 2-tuple")

    def __iter__(self):
        return self.sub_states.itervalues()

    def iter_initial(self):
        state = self.initial
        while state is not None:
            yield state
            state = state.initial

    def _get_transitions(self, old_path, trigger):
        """
        gets the correct transitions when transitions are triggered obj.some_trigger() with argument 'trigger' the
         name of the trigger.
         """
        for path in old_path.iter_paths():
            if (path, trigger) in self.triggering:
                return self.triggering[path, trigger]
        try:
            return self[old_path[0]]._get_transitions(old_path[1:], trigger)
        except IndexError:
            raise TransitionError("trigger '%s' does not exist for state '%s'" % (trigger, old_path))

    def _get_transition(self, old_path, new_path):
        """ get the correct transition when the state of an statefull object is set (obj.state = "some_state")"""
        for old_p in reversed(list(old_path.iter_paths())):
            for new_p in reversed(list(new_path.iter_paths())):
                if (old_p, new_p) in self.transitions:
                    return self.transitions[old_p, new_p]
        if len(old_path) and len(new_path) and  old_path[0] == new_path[0]:
            return self[old_path[0]]._get_transition(old_path[1:], new_path[1:])
        raise TransitionError("transition <%s, %s> does not exist" % (old_path, new_path))

    def do_trigger(self, obj, trigger, *args, **kwargs):
        """ Executes the transition when called through a trigger """
        for transition in self._get_transitions(obj.state_path, trigger):
            if transition.execute(obj, *args, **kwargs):
                return True
        return False

    def set_state(self, obj, state_path):
        """ Executes the transition when called by setting the state: obj.state = 'some_state' """
        if not self._get_transition(obj.state_path, state_path).execute(obj):
            raise SetStateError("conditional transition <%s, %s> failed"  % (obj.state, state_path))


class StateMachine(ChildState, ParentState):
    pass


class StateObject(object):
    """
    Base class for objects with a state machine managed state. BaseState can change by calling triggers as defined in
    transitions or by setting the 'state' property.
    """

    def __init__(self, initial=None, *args, **kwargs):
        """
        Constructor for the base class
        :param initial: string indicating the initial state of the object; if None, take first state of machine
        :param args: any arguments to be passed to super constructor in case of inheritance
        :param kwargs: any keyword arguments to be passed to super constructor in case of inheritance
        """
        super(StateObject, self).__init__(*args, **kwargs)
        self._new_state = self._get_initial(initial)
        self._old_state = None

    def _get_initial(self, initial):
        """checks initial and takes initial if given, else takes inital state name from state machine"""
        if initial:
            initial = Path(initial)
            if initial.has_in(self.machine):
                return initial
            raise ValueError("initial state does not exist")
        else:
            if self.machine.initial is not None:
                return self.machine.initial.path
            raise ValueError("no initial state is configured in state machine")

    def __getattr__(self, trigger):
        """
        Allows calling the triggers to cause a transition; the triggers return a bool indicating whether the
            transition took place.
        :param trigger: name of the trigger
        :return: partial function that allows the trigger to be called like object.some_trigger()
        """
        if trigger in self.machine.triggers:
            return partial(self.machine.do_trigger, obj=self, trigger=trigger)
        raise AttributeError("'%s' object has no attribute '%s'" % (type(self).__name__, trigger))

    @property
    def state_path(self):
        return self._new_state

    def store_state(self):
        self._old_state = self._new_state

    def get_state(self):
        """ returns the current state """
        return str(self._new_state)

    def set_state(self, state):
        """ Causes the state machine to call all relevant callbacks and change the state of the object """
        self.machine.set_state(self, Path(state))

    state = property(get_state, set_state)  # turn state into a property


if __name__ == "__main__":
    """
    Small usage example: a minimal state machine (see also the tests)
    """
    def printer(action):
        def func(obj):
            print "'%s' for '%s' results in transition <%s, %s>" % (action, str(obj), obj._old_state, obj._new_state)
        return func

    class LightSwitch(StateObject):

        machine = StateMachine(
            name="matter machine",
            states=[
                {"name": "on", "on_exit": printer("turn off"), "on_entry": printer("turn on")},
                {"name": "off",  "on_exit": printer("turn on"), "on_entry": printer("turn off")},
            ],
            transitions=[
                {"old_state": "off", "new_state": "on", "triggers": ["turn_on", "switch"]},
                {"old_state": "on", "new_state": "off", "triggers": ["turn_off", "switch"]},
            ],
        )

        def __init__(self, name, initial="off"):
            super(LightSwitch, self).__init__(initial=initial)
            self.name = name

        def __str__(self):
            return self.name + " (%s)" % self.state

    light_switch = LightSwitch("lights")

    print light_switch.turn_on()
    print light_switch, light_switch._new_state
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
    try:
        light_switch.state = "off"  # does not result in any callbacks because the switch is already off
    except TransitionError as e:
        print e.message


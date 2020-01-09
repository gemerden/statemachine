import json
from copy import deepcopy
from contextlib import contextmanager
from collections import defaultdict
from typing import Mapping

from states.tools import Path

__author__  = "lars van gemerden"


def listify(list_or_item):
    """utitity function to ensure an argument becomes a list if it is not one yet"""
    if isinstance(list_or_item, (list, tuple, set)):
        return list(list_or_item)
    else:
        return [list_or_item]

def dummy(*args, **kwargs):
    return True

def callbackify(callbacks):
    """
    Turns one or multiple callback functions or their names into one callback functions. Names will be looked up on the
    first argument (obj) of the actual call to the callback.

    :param callbacks: single or list of functions or method names, all with the same signature
    :return: new function that performs all the callbacks when called
    """
    callbacks = listify(callbacks)

    def result_callback(obj, *args, **kwargs):
        result = []  #  introduced to be able to use this method for "condition" callback to return a value
        for callback in callbacks:
            if isinstance(callback, str):
                result.append(getattr(obj, callback)(*args, **kwargs))
            else:
                result.append(callback(obj, *args, **kwargs))
        return all(result)

    return result_callback


def nameify(f, cast=lambda v: v):
    """ tries to give a name to an item"""
    return ".".join([f.__module__, f.__name__]) if callable(f) else getattr(f, "name", cast(f))


def replace_in_list(lst, old_item, new_items):
    """ replaces single old_item with a list new_item(s), retaining order of new_items """
    new_items = listify(new_items)
    index = lst.index(old_item)
    lst.remove(old_item)
    for i, item in enumerate(new_items):
        lst.insert(index+i, item)
    return lst


def has_doubles(lst):  # slow, O(n^2)
    return any(lst.count(l) > 1 for l in lst)


class MachineError(ValueError):
    """Exception indicating an error in the construction of the state machine"""
    pass


class TransitionError(ValueError):
    """Exception indicating an error in the in a state transition of an object"""
    pass


class Transition(object):
    """class for the internal representation of transitions in the state machine"""
    def __init__(self, machine, old_state, new_state, trigger, on_transfer=(), condition=None, info=""):
        self.machine = machine
        self.trigger = trigger
        self.old_path = Path(old_state)
        self.new_path = Path(new_state)
        self._validate(old_state, new_state)
        try:
            self.old_state = self.old_path.get_in(machine)
            self.new_state = self.new_path.get_in(machine)
        except KeyError as e:
            raise MachineError(f"non-existing state {e} when constructing transitions")
        self.on_transfer = callbackify(on_transfer)
        self.condition = callbackify(condition) if condition else None
        self.info = info

    def _validate(self, old_state, new_state):
        """ assures that no internal transitions are defined on an outer state level"""
        old_states = old_state.split(".", 1)
        new_states = new_state.split(".", 1)
        if (len(old_states) > 1 or len(new_states) > 1) and old_states[0] == new_states[0]:
            raise MachineError("inner transitions in a nested state machine cannot be defined at the outer level")

    def update_state(self, obj):
        obj._state = str(self.machine.full_path + self.new_path + self.new_path.get_in(self.machine).initial_path)

    @contextmanager
    def transitioning(self, obj):
        """ contextmanager to restore the previous state when any exception is raised in the callbacks """
        old_state = obj._state
        try:
            yield
        except BaseException:
            obj._state = old_state
            raise

    def _execute(self, obj, *args, **kwargs):
        self.machine.do_prepare(obj, *args, **kwargs)
        if ((not self.condition or self.condition(obj, *args, **kwargs)) and
            (not self.new_state.condition or self.new_state.condition(obj, *args, **kwargs))):
            self.machine.do_exit(obj, *args, **kwargs)
            self.on_transfer(obj, *args, **kwargs)
            self.update_state(obj)
            self.machine.do_enter(obj, *args, **kwargs)
            return True
        return False

    def execute(self, obj, *args, **kwargs):
        """
        Method calling all the callbacks of a state transition ans changing the actual object state (if condition
        returns True).
        :param obj: object of which the state is managed
        :param args: arguments of the callback
        :param kwargs: keyword arguments of the callback
        :return: bool, whether the transition took place
        """
        with self.transitioning(obj):
            context_manager = self.machine.get_context_manager()
            if context_manager:
                with context_manager(obj, **kwargs) as context:
                    return self._execute(obj, context=context, *args, **kwargs)
            else:
                return self._execute(obj, *args, **kwargs)

    def __str__(self):
        """string representing the transition"""
        return "<%s, %s>" %(str(self.old_path), str(self.new_path))


class BaseState(object):
    """base class for the both ChildState and ParentState"""
    def __init__(self, name, info="", *args, **kwargs):
        """
        Constructor of BaseState:

        :param name: name of the state, must be unique within the parent state machine
        """
        super(BaseState, self).__init__(*args, **kwargs)
        self.name = self._check_name(name)
        self.info = info

    def _check_name(self, name, exclude=(".", "*", "[", "]")):
        if any(c in name for c in exclude):
            raise MachineError("state name cannot contain characters %s" % exclude)
        return name


class StateParent(BaseState):
    """ class representing and handling the substates of a state """

    transition_class = Transition  # class used for the internal representation of transitions

    def __init__(self, name="root", states=(), transitions=(), initial=None,
                 prepare=(), before_any_exit=(), after_any_entry=(), context_manager=None, *args, **kwargs):
        """
        Constructor of the state machine, used to define all properties of the machine.
        :param states: a dict {name: {prop_name: property}} of state properties:
        state_name: {
            "on_entry":[some_method, ..],  # callback function(s) called when an object enters the state (single or list)
            "on_exit":[some_method, ..]  # callback function(s) called when an object exits the state (single or list)
        }
        :param transitions: a list of transition properties:
        {
            "old_state": "solid",  # the name of the 'from' state of the transition
            "new_state": "liquid",  # the name of the 'to' state of the transition
            "trigger": ["melt", "heat"],  # name of the trigger(s) triggering the transition: e.g. obj.heat()
            "on_transfer": [printer],# callback function called when an objects transfers from state to
                state(single or list)
            "condition": function(obj); called to determine whether a transtion will actually take place (return
                True to cause state change)
        }
        :param initial: optional name of the initial state
        :param before_any_exit: callback function called before an objects exits any state (single or list)
        :param after_any_entry: callback function called after an objects enters any state (single or list)
        :param context_manager: context manager callback that context for other callbacks to run in (e.g. open and close a file)

        Note that all callback functions (including 'condition') have the signature:
            func(obj, **kwargs); trigger(s)can pass the args and kwargs
        """
        super(StateParent, self).__init__(name=name, *args, **kwargs)
        self.sub_states = self._create_states(states)
        self.triggering = self._create_triggering(transitions)
        self.before_any_exit = callbackify(before_any_exit)
        self.after_any_entry = callbackify(after_any_entry)
        self.prepare = callbackify(prepare)
        self.context_manager = self._get_context_manager(context_manager)
        self.initial_state = self._get_initial_state(initial)
        self.triggers = self._get_triggers()

    def _get_initial_state(self, initial):
        if initial:
            return self.sub_states[initial]
        elif len(self.sub_states):
            return self.sub_states[list(self.sub_states.keys())[0]]

    def _get_triggers(self):
        """ gets a set of all trigger names in the state amchine and all sub states recursively """
        triggers = set(t[1] for t in self.triggering)
        for state in self:
            triggers.update(state._get_triggers())
        return triggers

    def _create_states(self, states):
        """creates a dictionary of state_name: BaseState key value pairs"""
        return {n: state_machine(machine=self, name=n, **p) for n, p in states.items()}

    def _create_transitions(self, transition_dicts):
        """creates a dictionary of (old state name, new state name): Transition key value pairs"""
        self._standardize_all(transition_dicts)
        self._expand_switches(transition_dicts)
        return self._expand_and_create(transition_dicts)

    def _standardize_all(self, transition_dicts, req_keys=("old_state", "new_state", "trigger")):
        def listify_state(state):
            if isinstance(state, str) and state.strip() == "*":
                return [s.name for s in self]
            else:
                return listify(state)

        for trans_dict in transition_dicts:
            for key in req_keys:
                if key not in trans_dict:
                    raise MachineError(f"key {key} missing from transition {trans_dict}")
            trans_dict["old_state"] = listify_state(trans_dict["old_state"])
            new_state = trans_dict["new_state"]
            if isinstance(new_state, Mapping):
                for switch in new_state.values():
                    switch["condition"] = listify(switch.get("condition", ()))
                    switch["on_transfer"] = listify(switch.get("on_transfer", ()))
            else:
                new_state = listify_state(new_state)
                if len(new_state) > 1:
                    raise MachineError(f"cannot have transition {trans_dict['new_state']}to multiple states without conditions")
                else:
                    trans_dict["new_state"] = new_state

            trans_dict["trigger"] = listify(trans_dict.get("trigger", ()))
            trans_dict["on_transfer"] = listify(trans_dict.get("on_transfer", ()))

    def _expand_switches(self, transition_dicts):
        """
        Replaces switched transitions with multiple transitions. A basic switched transition looks like:
        {
            "old_state": "state_name",
            "new_states": [
                {"name": "state_name_1", "condition": condition_func_1},
                {"name": "state_name_2", "condition": condition_func_2},
                {"name": "state_name_3"}  # no condition means default
            ],
            trigger = ["..."]
        }
        Note that transitions will be checked in order of appearance in new_states.

        :param transition_dicts: the transition configurations
        :return: transition configurations where switched transitions have been replaced with
                 multiple 'normal' transitions
        """
        for trans_dict in transition_dicts[:]:
            if isinstance(trans_dict["new_state"], Mapping):
                if "condition" in trans_dict:
                    raise MachineError("switched transitions cannot have a new state independent 'condition'")
                try:
                    new_transition_dicts = []
                    for new_state, switch in trans_dict["new_state"].items():
                        new_trans_dict = trans_dict.copy()
                        new_trans_dict.update(new_state=[new_state],
                                              on_transfer=trans_dict["on_transfer"] + switch["on_transfer"],
                                              condition=switch["condition"])
                        new_transition_dicts.append(new_trans_dict)
                    replace_in_list(transition_dicts, trans_dict, new_transition_dicts)
                except KeyError as e:
                    raise MachineError("missing parameter '%s' in switched transition" % e)

    def _expand_and_create(self, transition_dicts):
        trans_class = self.transition_class
        transitions = []
        for trans_dict in transition_dicts[:]:
            if len(trans_dict["new_state"]) > 1:
                if len(trans_dict["trigger"]):
                    raise MachineError("transition %s has multiple unconditional end-states" % str(trans_dict))
            for trigger in trans_dict.pop("trigger", ()):
                for old_state in trans_dict["old_state"]:
                    for new_state in trans_dict["new_state"]:
                        new_trans_dict = trans_dict.copy()
                        new_trans_dict.update(old_state=old_state,
                                              new_state=new_state)
                        transitions.append(trans_class(machine=self, trigger=trigger, **new_trans_dict))
        return transitions

    def _create_triggering(self, transition_dicts):
        """creates a dictionary of (old state name/path, trigger name): Transition key value pairs"""
        transitions = self._create_transitions(transition_dicts)
        trigger_dict = defaultdict(list)
        for transition in transitions:
            trigger_dict[transition.old_path, transition.trigger].append(transition)
        return self._check_triggering(trigger_dict)

    def _check_triggering(self, trigger_dict):
        """checks whether there are transitions that will never be reached and raises an error if so """
        seen = set()
        for (old_state, trigger), transitions in trigger_dict.items():
            for i, transition in enumerate(transitions[:-1]):
                if not (transition.condition or transition.new_state.condition):
                    raise MachineError("unreachable transition %s for trigger %s" % (str(transitions[i+1]), trigger))
            for transition in transitions:
                key = (old_state, transition.new_state, trigger)
                if key in seen:
                    raise MachineError(f"transition {old_state}, {transition.new_state} and trigger {trigger} already exists")
                seen.add(key)
        return trigger_dict

    def _get_context_manager(self, context_manager):
        if context_manager:
            if isinstance(context_manager, str):
                def new_context_manager(obj, *args, **kwargs):
                    return getattr(obj, context_manager)(*args, **kwargs)
                return new_context_manager
            else:
                return context_manager

    def __len__(self):
        """ number of sub-states """
        return len(self.sub_states)

    def __contains__(self, key):
        """ return whether the key exists in states or transitions """
        try:
            self[key]
        except KeyError:
            return False
        else:
            return True

    def __getitem__(self, key):
        """
        Gets sub states according to string key or transition according to the 2-tuple (e.g.
            key: ("on.washing", "off.broken"))
        """
        if isinstance(key, str):
            return self.sub_states[key]
        elif isinstance(key, tuple) and len(key) == 2:
            return self.triggering[Path(key[0]), key[1]]
        raise KeyError("key is not a string or 2-tuple")

    def __iter__(self):
        """ runs through sub_states, not keys/state-names """
        return iter(self.sub_states.values())

    def iter_initial(self, include_self=False):
        """ iterates into nested states, yielding the initial state of every sub-statemachine"""
        if include_self:
            yield self
        state = self.initial_state
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
        return self[old_path[0]]._get_transitions(old_path[1:], trigger)

    def trigger(self, obj, trigger, *args, **kwargs):
        """ Executes the transition when called through a trigger """
        for transition in self._get_transitions(Path(obj.state), trigger):
            if transition.execute(obj=obj, *args, **kwargs):
                return True
        return False

    def get_trigger(self, obj, trigger):
        """ Executes the transition when called through a trigger """
        def inner_trigger(*args, **kwargs):
            for transition in self._get_transitions(Path(obj.state), trigger):
                if transition.execute(obj, *args, **kwargs):
                    return True
            return False
        return inner_trigger


class State(BaseState):
    """class for the internal representation of a state without substates in the state machine"""

    def __init__(self, machine=None, on_entry=(), on_exit=(), condition=(), *args, **kwargs):
        """
        Constructor of ChildState:

        :param machine: state machine that contains this state
        :param on_entry: callback(s) that will be called, when an object enters this state
        :param on_exit: callback(s) that will be called, when an object exits this state
        :param condition: callback(s) (all()) that determine whether entry in this state is allowed
        """
        super(State, self).__init__(*args, **kwargs)
        self.machine = machine
        self.on_entry = callbackify(on_entry)
        self.on_exit = callbackify(on_exit)
        self.condition = callbackify(condition) if condition else None
        self.initial_path = Path()
        self.before_entry = []
        self.after_entry = []
        self.before_exit = []
        self.after_exit = []

    @property
    def full_path(self):
        """ returns the path from the top state machine to this state """
        try:
            return self.__full_path
        except AttributeError:
            self.__full_path = Path(reversed([s.name for s in self.iter_up()]))
            return self.__full_path

    @property
    def root_machine(self):
        machine = self
        while machine.machine is not None:
            machine = machine.machine
        return machine

    def _exit(self, obj, *args, **kwargs):
        self.machine.before_any_exit(obj, *args, **kwargs)
        for callback in self.before_exit:
            callback(obj, *args, **kwargs)
        self.on_exit(obj, *args, **kwargs)
        for callback in self.after_exit:
            callback(obj, *args, **kwargs)

    def _enter(self, obj, *args, **kwargs):
        for callback in self.before_entry:
            callback(obj, *args, **kwargs)
        self.on_entry(obj, *args, **kwargs)
        for callback in self.after_entry:
            callback(obj, *args, **kwargs)
        self.machine.after_any_entry(obj, *args, **kwargs)

    def _get_transitions(self, old_path, trigger):
        raise TransitionError("trigger '%s' does not exist for this state '%s'" % (trigger, self.name))

    def prepare(self, *args, **kwargs):
        pass

    def _get_triggers(self):
        return ()

    def get_nested_initial_state(self):
        return self

    def iter_up(self, include_root=False):
        """iterates over all states from this state to the top containing state"""
        state = self
        while state.machine is not None:
            yield state
            state = state.machine
        if include_root:
            yield state

    def __str__(self):
        return str(self.full_path)


class StateMachine(StateParent, State):
    """
    This class represents each state with substates in the state machine, as well as the state machine itself (basically
    saying that each state can be a state machine, and vice versa). Of course the root machine will never be entered or
    exited and states without substates will not have transitions, etc., but only one state_machine class representing all
    states and (nested) machines, simplifies navigation in case of transitions considerably.

    The arguments passed to the constructor (__init__) determine whether the state is a 'root'/'top' state machine,
    a nested state & machine or just a state; e.g. the root state machine does not have an on_exit/on_entry (because
    the object can never leave that state), states without sub-states do not get 'states' and 'transitions' arguments
    and nested state machines get both. See constructors for ChildState and ParentState for possible arguments.
    """
    def __init__(self, **kwargs):
        self.config = self._config(**kwargs)
        super(StateMachine, self).__init__(**kwargs)
        self.initial_path = self.get_initial_path()

    def get_initial_path(self, initial=None):
        """ returns the path string to the actual initial state the object will be in """
        try:
            full_initial_path = Path(initial or ()).get_in(self).get_nested_initial_state().full_path
        except KeyError:
            raise TransitionError("state '%s' does not exist in state '%s'" % (initial, self.name))
        return full_initial_path.tail(self.full_path)

    def do_prepare(self, obj, *args, **kwargs):
        for state in Path(obj.state).tail(self.full_path).iter_out(self, include=True):
            state.prepare(obj, *args, **kwargs)

    def do_exit(self, obj, *args, **kwargs):
        for state in Path(obj.state).tail(self.full_path).iter_out(self):
            state._exit(obj, *args, **kwargs)

    def do_enter(self, obj, *args, **kwargs):
        for state in Path(obj.state).tail(self.full_path).iter_in(self):
            state._enter(obj, *args, **kwargs)

    def get_context_manager(self):
        machine = self
        while machine.machine and not machine.context_manager:
            machine = machine.machine
        return machine.context_manager

    def get_nested_initial_state(self):
        state = self.initial_state
        while getattr(state, "initial_state", False):
            state = state.initial_state
        return state

    def _config(self, **kwargs):
        """ deepcopy can be a problem with non-toplevel callbacks """
        kwargs = deepcopy(kwargs)
        def convert(item):
            if isinstance(item, str):
                return item
            return nameify(item)
        return Path.apply_all(kwargs, convert)

    def __repr__(self):
        """
        :return: A JSON representation of the state machine, similar to the arguments of the state machine
                 constructor, but the callback methods have been replaced by 'module.name' of the callback
                 (so it cannot (yet) be used as constructor arguments).
        """
        return json.dumps(self.config, indent=4)


def state_machine(**config):
    if "states" in config:
        return StateMachine(**config)
    return State(**config)


class StatefulObject(object):
    """
    Base class for objects with a state machine managed state. State can change by calling triggers as defined in
    transitions of the state machine or by setting the 'state' property.

    Note that self.machine must return the state machine of the object. This can be achieved by either:

     - setting it at class level of the sub-class,
     - setting it in the constructor of the sub-class,
     - creating a property returning the state machine in the subclass.

     The last 2 allow for different machines to be used for objects of the same class.
    """

    def __init__(self, initial=None, *args, **kwargs):
        """
        Constructor for this base class
        :param initial: a ('.' separated) string indicating the initial (sub-)state of the object; if not given, take
                the initial state as configured in the machine (either explicit or the first in the list of states).
        """
        super(StatefulObject, self).__init__(*args, **kwargs)
        self._state = str(self.machine.get_initial_path(initial))

    def trigger_initial(self, **kwargs):
        """
        use this to call the 'on_entry' callbacks of the initial state, just after initialization, can be used if
        e.g. the instance must first get an ID by committing to database. Otherwise use if necessary.
        """
        self.machine.do_enter(self, **kwargs)

    def __getattr__(self, trigger):
        """
        Allows calling the triggers as methods to cause a transition; the triggers return a boolean indicating
            whether the transition took place.
        :param trigger: name of the trigger
        :return: partial function that allows the trigger to be called like obj.some_trigger(*args, **kwargs)
        """
        if trigger in self.machine.triggers:
            return self.machine.get_trigger(obj=self, trigger=trigger)
        raise AttributeError("'%s' object has no attribute '%s'" % (type(self).__name__, trigger))

    @property
    def state(self):
        """ returns the current (nested) state, as a '.' separated string """
        return self._state

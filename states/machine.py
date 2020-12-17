import json
from copy import deepcopy
from collections import defaultdict
from functools import partial
from operator import attrgetter
from typing import Mapping

from states.tools import MachineError, TransitionError, lazy_property, dummy_context
from states.tools import Path, listify, callbackify, nameify

__author__ = "lars van gemerden"

from states.transition import Transition


class BaseState(object):
    """Base class for the both ChildState and ParentState"""

    @classmethod
    def _check_name(cls, name, exclude=(".", "*", "[", "]", "(", ")")):
        if name.startswith('_'):
            raise MachineError("state or machine name cannot start with an '_'")
        if any(c in name for c in exclude):
            raise MachineError("state or machine name cannot contain characters %s" % exclude)
        return name

    def __init__(self, prepare=(), info="", *args, **kwargs):
        """
        Constructor of BaseState:

        :param info: (str), description of the state for auto docs
        """
        super().__init__(*args, **kwargs)
        self.prepare = callbackify(prepare)
        self.info = info

    @lazy_property
    def root(self):
        state = self
        while True:
            try:
                state = state.parent
            except AttributeError:
                return state

    @lazy_property
    def first_leaf_state(self):
        state = self
        while isinstance(state, ParentState):
            state = state.first_state
        return state

    @lazy_property
    def default_path(self):
        return self.first_leaf_state.full_path

    @property
    def full_path(self):
        """ returns the path from the top state machine to this state """
        return Path(reversed([s.name for s in self.iter_up()]))

    def iter_up(self, include_root=False):
        """iterates over all states from this state to the top containing state"""
        state = self
        while isinstance(state, ChildState):
            yield state
            state = state.parent
        if include_root:
            yield state

    def get_state(self, obj):
        return self.root.__get__(obj)

    def get_path(self, obj):
        return Path(self.root.__get__(obj))


class ChildState(BaseState):
    """ internal representation of a state without substates in the state machine"""

    def __init__(self, name, parent=None, on_entry=(), on_exit=(), condition=None, *args, **kwargs):
        """
        Constructor of ChildState:

        :param name: name and key in parent.sub_states of the child state
        :param parent: state machine that contains this state
        :param on_entry: callback(s) that will be called, when an object enters this state
        :param on_exit: callback(s) that will be called, when an object exits this state
        :param condition: callback(s) (all()) that determine whether entry in this state is allowed
        """
        super(ChildState, self).__init__(*args, **kwargs)
        self.name = self._check_name(name)
        self.parent = parent
        self.on_entry = callbackify(on_entry)
        self.on_exit = callbackify(on_exit)
        self.condition = callbackify(condition)

    def _get_transitions(self, old_path, trigger):
        raise TransitionError(f"trigger '{trigger}' does not exist for this state '{old_path}'")

    def __str__(self):
        return str(self.full_path)


class ParentState(BaseState):
    """ class representing and handling the substates of a state """

    def __init__(self, states=(), transitions=(),
                 before_any_exit=(), after_any_entry=(),
                 context_manager=dummy_context, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sub_states = self._create_states(states)
        self.triggering = self._create_triggering(transitions)
        self.before_any_exit = callbackify(before_any_exit)
        self.after_any_entry = callbackify(after_any_entry)
        self.context_manager = self._get_context_manager(context_manager)

    @lazy_property
    def first_state(self):
        return self.sub_states[list(self.sub_states.keys())[0]]  # top state

    @lazy_property
    def triggers(self):
        """ gets a set of all trigger names in the state machine and all sub states recursively """
        triggers = set(t[1] for t in self.triggering)
        for state in self.sub_states.values():
            if isinstance(state, ParentState):
                triggers.update(state.triggers)
        return triggers

    def _get_context_manager(self, context_manager):
        if isinstance(context_manager, str):
            def new_context_manager(obj, *args, **kwargs):
                return getattr(obj, context_manager)(*args, **kwargs)

            return new_context_manager
        return context_manager

    def _create_states(self, states):
        """creates a dictionary of state_name: BaseState key value pairs"""
        return {n: state_machine(name=n, parent=self, **p) for n, p in states.items()}

    def _create_transitions(self, transition_dicts):
        """creates a dictionary of (old state name, new state name): Transition key value pairs"""
        transition_dicts = self._standardize_all(transition_dicts)
        transition_dicts = self._expand_switches(transition_dicts)
        return self._expand_and_create(transition_dicts)

    def _standardize_all(self, transition_dicts, req_keys=("old_state", "new_state", "trigger")):
        def listify_state(state):
            if isinstance(state, str) and state.strip() == "*":
                return [s.name for s in self]
            else:
                return listify(state)

        new_transition_dicts = []
        for trans_dict in transition_dicts:
            for key in req_keys:
                if key not in trans_dict:
                    raise MachineError(f"key {key} missing from transition {trans_dict}")

            for old_state in listify_state(trans_dict["old_state"]):
                new_trans_dict = deepcopy(trans_dict)
                new_trans_dict["old_state"] = old_state
                new_state = new_trans_dict["new_state"]
                if isinstance(new_state, Mapping):
                    for switch in new_state.values():
                        switch["condition"] = listify(switch.get("condition", ()))
                        switch["after_transfer"] = listify(switch.pop("on_transfer", ()))
                else:
                    if len(listify_state(new_state)) > 1:
                        raise MachineError(
                            f"cannot have transition {trans_dict['new_state']}to multiple states without conditions")
                    else:
                        trans_dict["new_state"] = new_state

                new_trans_dict["trigger"] = listify(trans_dict.get("trigger", ()))
                new_trans_dict["before_transfer"] = listify(new_trans_dict.pop("on_transfer", ()))
                new_transition_dicts.append(new_trans_dict)
        return new_transition_dicts

    def _expand_switches(self, transition_dicts):
        """
        Replaces switched transitions with multiple transitions. A basic switched transition looks like:
        {
            "old_state": "state_name",
            "new_states": {
                "state_name_1": {"condition": condition_func_1},
                "state_name_2": {"condition": condition_func_2},
                "state_name_3": {}  # no condition means default
            },
            trigger = ["..."]
        }
        Note that transitions will be checked in order of appearance in new_states.

        :param transition_dicts: the transition configurations
        :return: transition configurations where switched transitions have been replaced with
                 multiple 'normal' transitions
        """
        new_transition_dicts = []
        for trans_dict in transition_dicts:
            if isinstance(trans_dict["new_state"], Mapping):
                if "condition" in trans_dict:
                    raise MachineError("switched transitions cannot have a new state independent 'condition'")
                try:

                    for new_state, switch in trans_dict["new_state"].items():
                        new_trans_dict = trans_dict.copy()
                        new_trans_dict.update(new_state=new_state, **switch)
                        new_transition_dicts.append(new_trans_dict)
                    if new_transition_dicts[-1]["condition"]:  # add default transition going back to old state
                        new_trans_dict = trans_dict.copy()
                        new_trans_dict.update(new_state=trans_dict['old_state'],
                                              condition=None,
                                              after_transfer=())
                        new_transition_dicts.append(new_trans_dict)
                except KeyError as e:
                    raise MachineError(f"missing parameter '{e}' in switched transition")
            else:
                new_transition_dicts.append(trans_dict)
        return new_transition_dicts

    def _expand_and_create(self, transition_dicts):
        transitions = []
        for trans_dict in transition_dicts[:]:
            if isinstance(trans_dict["new_state"], Mapping):
                if len(trans_dict["trigger"]):
                    raise MachineError(f"transition {str(trans_dict)} has multiple unconditional end-states")
            for trigger in trans_dict.pop("trigger", ()):
                transitions.append(Transition(machine=self, trigger=trigger, **trans_dict))
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
                    raise MachineError(f"unreachable transition {str(transitions[i + 1])} for trigger '{trigger}'")
            for transition in transitions:
                key = (old_state, transition.new_state, trigger)
                if key in seen:
                    raise MachineError(f"transition {old_state}, {transition.new_state} and trigger {trigger} already exists")
                seen.add(key)
        return trigger_dict

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
        raise KeyError(f"key '{key}' is not a string or 2-tuple")

    def __iter__(self):
        """ runs through sub_states, not keys/state-names """
        yield from self.sub_states.values()

    @lazy_property
    def states(self):
        """ the names of the states """
        return list(self.sub_states)

    @lazy_property
    def transitions(self):
        """ 2-tuples of the old and new state names of all transitions """
        all_transitions = set()
        for transitions in self.triggering.values():
            for transition in transitions:
                all_transitions.add((str(transition.old_path), str(transition.new_path)))
        return all_transitions

    def do_prepare(self, obj, *args, _path=None, **kwargs):
        for state in self.get_path(obj).tail(self.full_path).iter_out(self, include=True):
            state.prepare(obj, *args, **kwargs)

    def do_exit(self, obj, *args, _path=None, **kwargs):
        for state in self.get_path(obj).tail(self.full_path).iter_out(self):
            state.parent.before_any_exit(obj, *args, **kwargs)
            state.on_exit(obj, *args, **kwargs)

    def do_enter(self, obj, *args, _path=None, **kwargs):
        for state in self.get_path(obj).tail(self.full_path).iter_in(self):
            state.on_entry(obj, *args, **kwargs)
            state.parent.after_any_entry(obj, *args, **kwargs)

    def _get_transitions(self, old_path, trigger_name):
        """
        gets the correct transitions when transitions are triggered obj.some_trigger() with argument 'trigger' the
         name of the trigger.
         """
        for path in old_path.iter_paths():
            if (path, trigger_name) in self.triggering:
                return self.triggering[path, trigger_name]
        return self[old_path[0]]._get_transitions(old_path[1:], trigger_name)


class LeafState(ChildState):
    default_path = Path()

    def __init__(self, *args, on_stay=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.on_stay = callbackify(on_stay)


class NestedMachine(ParentState, ChildState):
    pass

class StateMachine(ParentState):
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
    full_path = Path()

    def __init__(self, **kwargs):
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
            "condition": function(obj); called to determine whether a transition will actually take place (return
                True to cause state change)
        }
        :param initial: optional name of the initial state
        :param before_any_exit: callback function called before an objects exits any state (single or list)
        :param after_any_entry: callback function called after an objects enters any state (single or list)
        :param context_manager: context manager callback that context for other callbacks to run in (e.g. open and close a file)

        Note that all callback functions (including 'condition') have the signature:
            func(obj, **kwargs); trigger(s)can pass the args and kwargs
        """
        self.name = None
        self.dkey = None
        self.config = self._config(**kwargs)
        super(StateMachine, self).__init__(**kwargs)
        self.initial_path = self.get_initial_path()

    def __set_name__(self, cls, name):
        self.name = self._check_name(name)
        self.dkey = '_' + self.name

        if not hasattr(cls, '_state_machines'):
            cls._state_machines = {}
        cls._state_machines[self.name] = self

        if not hasattr(cls, '_trigger_func_dict'):
            cls._trigger_func_dict = defaultdict(list)

        for trigger_name in self.triggers:
            func_list = cls._trigger_func_dict[trigger_name]
            func_list.append(partial(self.trigger, trigger_name=trigger_name))

            def trigger_func(*args, _func_list=func_list, **kwargs):
                obj = None
                for func in _func_list:
                    obj = func(*args, **kwargs)  # same 'obj' every time
                return obj
            setattr(cls, trigger_name, trigger_func)

    def __get__(self, obj, cls=None):
        if obj is None:
            return self
        return obj.__dict__[self.dkey]

    def __set__(self, obj, state_name):
        if self.dkey in obj.__dict__:
            raise AttributeError(f"{self.name} of {type(obj).__name__} cannot be changed directly; use triggers instead")
        setattr(obj, self.dkey, state_name)

    def get_initial_path(self, initial=""):
        """ returns the path string to the actual initial state the object will be in """
        try:
            return Path(initial).get_in(self).first_leaf_state.full_path
        except KeyError:
            raise TransitionError(f"state '{initial}' does not exist in state machine '{self.name}'")

    def get_trigger_func(self, trigger_name):
        if trigger_name not in self.triggers:
            raise TransitionError
        return partial(self.trigger, trigger_name=trigger_name)

    def trigger(self, obj, trigger_name, *args, **kwargs):
        """ Executes the transition when called through a trigger """
        for transition in self._get_transitions(self.get_path(obj), trigger_name):
            if transition.execute(obj, *args, **kwargs):
                break
        return obj

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
        if "name" in config:
            return NestedMachine(**config)
        else:
            return StateMachine(**config)
    return LeafState(**config)


if __name__ == '__main__':
    pass

__author__ = "lars van gemerden"

import json
from copy import deepcopy
from collections import defaultdict, deque
from functools import partial
from typing import Mapping, Sequence, Set

from states.standardize import get_expanded_paths, get_spliced_paths, get_expanded_state_names, validate_new_state, \
    standardize_statemachine_config
from states.tools import MachineError, TransitionError, lazy_property, listify, do_callbacks, copy_struct
from states.tools import Path, nameify

from states.transition import Transition


class BaseState(object):
    """Base class for the both ChildState and ParentState"""

    @classmethod
    def _validate_name(cls, name, exclude=(".", "*", "[", "]", "(", ")")):
        if name.startswith('_'):
            raise MachineError(f"state or machine name '{name}' cannot start with an '_'")
        if any(c in name for c in exclude):
            raise MachineError(f"state or machine name '{name}' cannot contain characters %s" % exclude)
        return name

    def __init__(self, prepare=(), info="", *args, **kwargs):
        """
        Constructor of BaseState:

        :param info: (str), description of the state for auto docs
        """
        super().__init__(*args, **kwargs)
        self._prepare = listify(prepare)
        self.info = info

    _do_callbacks = do_callbacks

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
        return self.first_leaf_state.full_path.tail(self.full_path)

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

    def __init__(self, name, parent=None, on_entry=(), on_exit=(), *args, **kwargs):
        """
        Constructor of ChildState:

        :param name: name and key in parent.sub_states of the child state
        :param parent: state machine that contains this state
        :param on_entry: callback(s) that will be called, when an object enters this state
        :param on_exit: callback(s) that will be called, when an object exits this state
        # :param condition: callback(s) (all()) that determine whether entry in this state is allowed
        """
        super(ChildState, self).__init__(*args, **kwargs)
        self.name = self._validate_name(name)
        self.parent = parent
        self._on_entry = listify(on_entry)
        self._on_exit = listify(on_exit)

    def _get_transitions(self, old_path, trigger):
        raise TransitionError(f"trigger '{trigger}' does not exist for this state '{self.name}'")

    def __str__(self):
        return str(self.full_path)


class ParentState(BaseState):
    """ class representing and handling the substates of a state """

    def __init__(self, states=(), transitions=(), *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._sub_states = self._create_states(states)
        self._trans_dict = self._create_transitions(transitions)
        self._triggering = self._create_triggering()

    @lazy_property
    def first_state(self):
        return self._sub_states[list(self._sub_states.keys())[0]]

    @lazy_property
    def triggers(self):
        """ gets a set of all trigger names in the state machine and all sub states recursively """
        triggers = set(t[1] for t in self._triggering)
        for state in self._sub_states.values():
            if isinstance(state, ParentState):
                triggers.update(state.triggers)
        return triggers

    def __len__(self):
        """ number of sub-states """
        return len(self._sub_states)

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
            return self._sub_states[key]
        elif isinstance(key, tuple) and len(key) == 2:
            return self._triggering[Path(key[0]), key[1]]
        raise KeyError(f"key '{key}' is not a string or 2-tuple")

    def __iter__(self):
        """ runs through sub_states, not keys/state-names """
        yield from self._sub_states

    @lazy_property
    def states(self):
        """ the names of the states """
        return list(self._sub_states)

    @lazy_property
    def transitions(self):
        """ 2-tuples of the old and new state names of all transitions """
        return [(str(old_path), str(new_path)) for old_path, new_path in self._trans_dict]

    def state_getter(self, path):
        return path.get_in(self)

    def do_prepare(self, obj, *args, **kwargs):
        for state in self.get_path(obj).tail(self.full_path).iter_out(self, include=True):
            state._do_callbacks('_prepare', obj, *args, **kwargs)

    def do_exit(self, obj, *args, **kwargs):
        for state in self.get_path(obj).tail(self.full_path).iter_out(self):
            state._do_callbacks('_on_exit', obj, *args, **kwargs)

    def do_entry(self, obj, *args, **kwargs):
        for state in self.get_path(obj).tail(self.full_path).iter_in(self):
            state._do_callbacks('_on_entry', obj, *args, **kwargs)

    def _create_states(self, states):
        """creates a dictionary of state_name: BaseState key value pairs"""
        state_dict = {}
        for name, config in states.items():
            config.update(name=name, parent=self)
            if config.get('states'):
                state_dict[name] = NestedMachine(**config)
            else:
                state_dict[name] = LeafState(**config)
        return state_dict

    def _create_transitions(self, transition_dicts):
        """creates a dictionary of (old state name, new state name): Transition key value pairs"""
        transition_dicts = self._standardize_all(transition_dicts)
        transition_dicts = self._expand_switches(transition_dicts)
        transitions = self._expand_and_create(transition_dicts)
        trans_dict = defaultdict(list)
        for transition in transitions:
            trans_dict[transition.old_path, transition.new_path].append(transition)
        return trans_dict

    def _standardize_all(self, transition_dicts, req_keys=("old_state", "new_state", "trigger")):
        def listify_state(state):
            if isinstance(state, str) and state.strip() == "*":
                return list(self)
            else:
                return listify(state)

        def get_list(dct, key):
            return listify(dct.get(key, ()))

        new_transition_dicts = []
        for trans_dict in transition_dicts:
            for key in req_keys:
                if key not in trans_dict:
                    raise MachineError(f"key {key} missing from transition {trans_dict}")

            old_states = listify(trans_dict["old_state"])
            for old_state_name in get_expanded_state_names(*old_states, state_getter=self.state_getter):
                new_trans_dict = deepcopy(trans_dict)
                new_trans_dict["old_state"] = old_state_name
                new_state = new_trans_dict["new_state"]
                if isinstance(new_state, Mapping):
                    for state_name, switch in new_state.items():
                        validate_new_state(state_name)
                        switch["condition"] = get_list(switch, "condition")
                        switch["on_transfer"] = get_list(switch, "on_transfer")
                else:
                    trans_dict["new_state"] = validate_new_state(new_state)

                new_trans_dict["trigger"] = get_list(trans_dict, "trigger")
                new_trans_dict["on_transfer"] = get_list(new_trans_dict, "on_transfer")
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
            old_state_name = trans_dict["old_state"]
            if isinstance(trans_dict["new_state"], Mapping):
                if trans_dict.get('condition'):
                    raise MachineError("switched transitions cannot have a new state independent 'condition'")
                try:
                    for new_state_name, switch in trans_dict["new_state"].items():
                        new_trans_dict = copy_struct(trans_dict)
                        new_trans_dict['on_transfer'].extend(switch.pop('on_transfer', []))
                        new_trans_dict.update(new_state=new_state_name, **switch)
                        new_transition_dicts.append(new_trans_dict)
                    if new_transition_dicts[-1]["condition"]:  # add default transition going back to old state
                        new_trans_dict = copy_struct(trans_dict)
                        new_trans_dict.update(new_state=trans_dict['old_state'],
                                              condition=(),
                                              on_transfer=())
                        new_transition_dicts.append(new_trans_dict)
                except KeyError as e:
                    raise MachineError(f"missing parameter '{e}' in switched transition")
            else:
                new_transition_dicts.append(trans_dict)
        return new_transition_dicts

    def _expand_and_create(self, transition_dicts):
        transitions = []
        for trans_dict in transition_dicts[:]:
            for trigger in trans_dict.pop("trigger"):
                transitions.append(Transition(machine=self, trigger=trigger, **trans_dict))
        return transitions

    def _create_triggering(self):
        """creates a dictionary of (old state name/path, trigger name): Transition key value pairs"""
        trigger_dict = defaultdict(list)
        for (old_path, _), transitions in self._trans_dict.items():
            for transition in transitions:
                trigger_dict[old_path, transition.trigger].append(transition)
        return self._check_triggering(trigger_dict)

    def _check_triggering(self, trigger_dict):
        """checks whether there are transitions that will never be reached and raises an error if so """
        seen = set()
        for (old_state, trigger), transitions in trigger_dict.items():
            for i, transition in enumerate(transitions[:-1]):
                if not (transition._condition):
                    raise MachineError(f"unreachable transition {str(transitions[i + 1])} for trigger '{trigger}'")
            for transition in transitions:
                key = (old_state, transition.new_state, trigger)
                if key in seen:
                    raise MachineError(
                        f"transition '{old_state}', '{transition.new_state}' and trigger '{trigger}' already exists")
                seen.add(key)
        return trigger_dict

    def _get_transitions(self, old_path, trigger_name):
        """
        gets the correct transitions when transitions are triggered obj.some_trigger() with argument 'trigger' the
         name of the trigger.
         """
        for path in old_path.iter_paths():
            if (path, trigger_name) in self._triggering:
                return self._triggering[path, trigger_name]
        return self[old_path[0]]._get_transitions(old_path[1:], trigger_name)


class LeafState(ChildState):
    default_path = Path()

    def __init__(self, *args, on_stay=(), **kwargs):
        super().__init__(*args, **kwargs)
        self._on_stay = listify(on_stay)


class NestedMachine(ParentState, ChildState):
    pass


class StateMachine(ParentState):
    """
    This class represents each state with substates in the state machine, as well as the state machine itself (basically
    saying that each state can be a state machine, and vice versa). Of course the root machine will never be entered or
    exited and states without substates will not have transitions, etc., but only one StateMachine class representing all
    states and (nested) machines, simplifies navigation in case of transitions considerably.

    The arguments passed to the constructor (__init__) determine whether the state is a 'root'/'top' state machine,
    a nested state & machine or just a state; e.g. the root state machine does not have an on_exit/on_entry (because
    the object can never leave that state), states without sub-states do not get 'states' and 'transitions' arguments
    and nested state machines get both. See constructors for ChildState and ParentState for possible arguments.
    """
    full_path = Path()

    def __init__(self, *args, **kwargs):
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
        :param on_any_exit: callback function called before an objects exits any state (single or list)
        :param on_any_entry: callback function called after an objects enters any state (single or list)
        :param context_manager: context manager callback that context for other callbacks to run in (e.g. open and close a file)

        Note that all callback functions (including 'condition') have the signature:
            func(obj, **kwargs); trigger(s)can pass the args and kwargs
        """
        super(StateMachine, self).__init__(*args, **kwargs)
        self.initial_path = self.get_initial_path()
        self.name = None
        self.dict_key = None

    def __set_name__(self, cls, name):
        self.name = self._validate_name(name)
        self.dict_key = '_' + self.name

    def __get__(self, obj, cls=None):
        if obj is None:
            return self
        return obj.__dict__[self.dict_key]

    def __set__(self, obj, state_name):
        if self.dict_key in obj.__dict__:
            raise AttributeError(f"{self.name} of {type(obj).__name__} cannot be changed directly; use triggers instead")
        setattr(obj, self.dict_key, state_name)

    def _register_callback(self, on_key, state_names):
        state_paths = get_expanded_paths(*state_names, state_getter=self.state_getter)
        states = [path.get_in(self) for path in state_paths] or [self]

        def register(func):
            for state in states:
                getattr(state, '_' + on_key).append(func)
            return func

        return register

    def on_entry(self, state_name, *state_names):
        return self._register_callback('on_entry', (state_name,) + state_names)

    def on_exit(self, state_name, *state_names):
        return self._register_callback('on_exit', (state_name,) + state_names)

    def on_stay(self, state_name, *state_names):
        return self._register_callback('on_stay', (state_name,) + state_names)

    def on_transfer(self, old_state_name, new_state_name):
        spliced_paths = get_spliced_paths(old_state_name, new_state_name, state_getter=self.state_getter)

        def register(func):
            success = False
            for common, old_tail, new_tail in spliced_paths:
                for transition in common.get_in(self)._trans_dict.get((old_tail, new_tail), ()):
                    if transition is not None:
                        transition._on_transfer.append(func)
                        success = True
            if not success:
                raise MachineError(f"'on_transfer' decorator has no effect: no transitions found to add callback to")
            return func

        return register

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
            if isinstance(item, tuple):
                return list(map(convert, item))
            return nameify(item)

        return Path.apply_all(kwargs, convert)

    def __repr__(self):
        """
        :return: A JSON representation of the state machine, similar to the arguments of the state machine
                 constructor, but the callback methods have been replaced by 'module.name' of the callback
                 (so it cannot (yet) be used as constructor arguments).
        """
        return json.dumps(self.config, indent=4)


def state_machine(states, transitions, **config):
    config = standardize_statemachine_config(states=states,
                                             transitions=transitions,
                                             **config)
    return StateMachine(**config)

if __name__ == '__main__':
    pass

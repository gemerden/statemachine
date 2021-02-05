__author__ = "lars van gemerden"

import json
from copy import deepcopy
from collections import defaultdict
from typing import Mapping

from states.callbacks import Callbacks
from states.standardize import get_expanded_paths, get_spliced_paths, standardize_statemachine_config, get_spliced_path
from states.tools import MachineError, TransitionError, lazy_property
from states.tools import Path, nameify

from states.transition import Transition

_marker = object()


class BaseState(object):
    """Base class for the both ChildState and ParentState"""

    @classmethod
    def _validate_name(cls, name, exclude=(".", "*", "[", "]", "(", ")")):
        if name.startswith('_'):
            raise MachineError(f"state or machine name '{name}' cannot start with an '_'")
        if any(c in name for c in exclude):
            raise MachineError(f"state or machine name '{name}' cannot contain characters %s" % exclude)
        return name

    def __init__(self, info="", **callbacks):
        """
        Constructor of BaseState:

        :param info: (str), description of the state for auto docs
        """
        self.callbacks = Callbacks(**callbacks)
        self.info = info

    @lazy_property
    def root(self):
        state = self
        while isinstance(state, ChildState):
            state = state.parent
        return state

    @lazy_property
    def first_leaf_state(self):
        state = self
        while isinstance(state, ParentState):
            state = state.first_state
        return state

    @lazy_property
    def default_path(self):
        """ returns the path to the actual initial state the object will be in """
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

    def __init__(self, name, parent=None, on_entry=(), on_exit=(), **kwargs):
        """
        Constructor of ChildState:

        :param name: name and key in parent.sub_states of the child state
        :param parent: state machine that contains this state
        :param on_entry: callback(s) that will be called, when an object enters this state
        :param on_exit: callback(s) that will be called, when an object exits this state
        # :param condition: callback(s) (all()) that determine whether entry in this state is allowed
        """
        super(ChildState, self).__init__(on_entry=on_entry, on_exit=on_exit, **kwargs)
        self.name = self._validate_name(name)
        self.parent = parent

    def _get_transitions(self, old_path, trigger):
        raise TransitionError(f"transition '{str(old_path)}' with trigger '{trigger}' does not exist for state '{self.name}'")

    def __str__(self):
        return str(self.full_path)


class ParentState(BaseState):
    """ class representing and handling the substates of a state """

    def __init__(self, states=(), transitions=(), **kwargs):
        super().__init__(**kwargs)
        self._sub_states = self._create_states(states)
        self._trans_dict = self._triggering = None
        self._insert_transitions(transitions)

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

    def _insert_transitions(self, transition_dicts):
        """creates a dictionary of (old state name, new state name): Transition key value pairs"""
        transitions = [Transition(machine=self, **td) for td in transition_dicts]
        trans_dict = defaultdict(list)
        triggering = defaultdict(list)
        for transition in transitions:
            trans_dict[transition.old_path, transition.new_path].append(transition)
            triggering[transition.old_path, transition.trigger].append(transition)
        self._trans_dict = dict(trans_dict)  # to stop items being created on access
        self._triggering = dict(triggering)

    @lazy_property
    def states(self):
        """ the names of the states """
        return list(self._sub_states)

    @lazy_property
    def transitions(self):
        """ 2-tuples of the old and new state names of all transitions """
        return [(str(old_path), str(new_path)) for old_path, new_path in self._trans_dict]

    @lazy_property
    def triggers(self):
        """ gets a set of all trigger names in the state machine and all sub states recursively """
        triggers = set(t[1] for t in self._triggering)
        for state in self._sub_states.values():
            if isinstance(state, ParentState):
                triggers.update(state.triggers)
        return triggers

    @lazy_property
    def first_state(self):
        return self._sub_states[list(self._sub_states)[0]]

    def __len__(self):
        """ number of sub-states """
        return len(self._sub_states)

    def __iter__(self):
        yield from self._sub_states

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
        elif isinstance(key, Path):
            return key.get_in(self)
        elif isinstance(key, tuple) and len(key) == 2:
            return self._trans_dict[Path(key[0]), Path(key[1])]
        raise KeyError(f"key '{key}' is not a string or 2-tuple")

    def _get_transitions(self, old_path, trigger):
        """
        gets the correct transitions when transitions are triggered obj.some_trigger() with argument 'trigger' the
         name of the trigger.
         """
        try:
            return self._triggering[old_path, trigger]
        except KeyError:
            return self[old_path[0]]._get_transitions(old_path[1:], trigger)


class LeafState(ChildState):
    default_path = Path()

    def __init__(self, on_stay=(), **kwargs):
        super().__init__(on_stay=on_stay, **kwargs)

    def __len__(self):
        return 0


class NestedMachine(ParentState, ChildState):
    pass


class StateMachine(ParentState, Mapping):
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

    def __init__(self, *args, prepare=(), **kwargs):
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
        super(StateMachine, self).__init__(*args, prepare=prepare, **kwargs)
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
            raise AttributeError(f"state {self.name} of {type(obj).__name__} cannot be changed directly; use triggers instead")
        setattr(obj, self.dict_key, state_name)

    def _iter_states(self, *state_names):
        state_paths = get_expanded_paths(*state_names,
                                         getter=lambda p: self[p])
        for path in state_paths:
            yield path.get_in(self)

    def _iter_transitions(self, old_state_name, new_state_name):
        spliced_paths = get_spliced_paths(old_state_name, new_state_name,
                                          getter=lambda p: self[p])
        for common, old_tail, new_tail in spliced_paths:
            yield from common.get_in(self)._trans_dict.get((old_tail, new_tail), ())

    def _register_callback(self, on_key, *state_names):
        states = list(self._iter_states(*state_names))

        def register(func):
            for state in states:
                state.callbacks.register(on_key, func)
            return func

        return register

    def on_entry(self, state_name, *state_names):
        return self._register_callback('on_entry', state_name, *state_names)

    def on_exit(self, state_name, *state_names):
        return self._register_callback('on_exit', state_name, *state_names)

    def on_stay(self, state_name, *state_names):
        return self._register_callback('on_stay', state_name, *state_names)

    def on_transfer(self, old_state_name, new_state_name):
        transitions = list(self._iter_transitions(old_state_name, new_state_name))
        if not len(transitions):
            raise MachineError(f"'on_transfer' decorator has no effect: no transitions found to add callback to")

        def register(func):
            for transition in transitions:
                transition.callbacks.register('on_transfer', func)
            return func

        return register

    def initial_entry(self, obj, *args, **kwargs):
        self.callbacks.prepare(obj, *args, **kwargs)
        for state in self.get_path(obj).iter_in(self):
            state.do_on_entry(obj, *args, **kwargs)

    def trigger(self, obj, trigger, *args, **kwargs):
        """ Executes the transition when called through a trigger """
        self.callbacks.prepare(obj, *args, **kwargs)
        for transition in self._get_transitions(self.get_path(obj), trigger):
            if transition.execute(obj, *args, **kwargs):
                break
        return obj

    def config(self, **kwargs):
        """ deepcopy can be a problem with non-toplevel callbacks """
        kwargs = deepcopy(kwargs)

        def convert(item):
            if isinstance(item, str):
                return item
            if isinstance(item, (list, tuple)):
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

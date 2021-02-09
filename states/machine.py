__author__ = "lars van gemerden"

import json
from typing import Mapping
from collections import defaultdict

from .exception import MachineError, TransitionError
from .callbacks import Callbacks
from .standardize import get_expanded_paths, get_spliced_paths, standardize_statemachine_config, get_extended_paths, \
    get_spliced_path
from .tools import lazy_property, Path
from .transition import Transition


def none_check(check, res, alt):
    return alt if check is None else res


class BaseState(Mapping):
    """Base class for the both StateMachine and any states in the machine"""

    @classmethod
    def _validate_name(cls, name, exclude=(".", "*", "[", "]", "(", ")")):
        if name is None:
            return None
        if not len(name.strip()):
            raise MachineError(f"state or state machine must have a name")
        if name.startswith('_'):
            raise MachineError(f"state or machine name '{name}' cannot start with an '_'")
        if any(c in name for c in exclude):
            raise MachineError(f"state or machine name '{name}' cannot contain characters %s" % exclude)
        return name

    def __init__(self, name=None, parent=None, states=None, transitions=(), on_entry=(), on_exit=(), on_stay=(), info="",
                 **callbacks):
        """
        Constructor of BaseState:
        :param name: state name and key in parent.sub_states
        :param parent: state machine that contains this state
        :param on_entry: callback(s) that will be called, when an object enters this state
        :param on_exit: callback(s) that will be called, when an object exits this state
        :param info: (str), description of the state for auto docs
        """
        self.callbacks = Callbacks(on_entry=on_entry, on_exit=on_exit, on_stay=on_stay, **callbacks)
        self.name = self._validate_name(name)
        self._init_parent(parent)
        self._init_states(states or {})
        self._init_transitions(transitions)
        self.info = info
        self.verified = False

    def _init_parent(self, parent):
        self.parent = parent
        if parent is None:
            self.path = Path()
            self.root = self
            self.up = [self]
        else:
            self.path = parent.path + self.name
            self.root = parent.root
            self.up = [self] + parent.up

    def _init_states(self, states):
        """creates a dictionary of state_name: BaseState key value pairs"""
        self.sub_states = {}
        for name, config in states.items():
            config.update(name=name, parent=self)
            self.sub_states[name] = State(**config)

    def _init_transitions(self, transition_dicts):
        """creates a dictionary of (old state name, new state name): Transition key value pairs"""
        self.trans_dict = defaultdict(list)
        self.triggering = defaultdict(list)
        for trans_dict in transition_dicts:
            self.append_transition(Transition(machine=self, **trans_dict))

    def _verify_transitions(self):
        for transitions in self.triggering.values():
            if transitions[-1].callbacks.has_any('condition'):
                raise MachineError(f"no default transition for transitions from "
                                   f"'{transitions[-1].old_state}' with trigger {transitions[-1].trigger}")
            for transition in transitions[:-1]:
                if not transition.callbacks.has_any('condition'):
                    raise MachineError(f"missing condition for transitions from "
                                       f"'{transitions[-1].old_state}' with trigger {transitions[-1].trigger}")
        for state in self.sub_states.values():
            state._verify_transitions()

    def verify(self):
        """ this method should only be executed once after all initialisation (including setting all callbacks) """
        if not self.verified:
            self._verify_transitions()
        self.verified = True

    def append_transition(self, transition):
        self.trans_dict[transition.old_path, transition.new_path].append(transition)
        self.triggering[transition.old_path, transition.trigger].append(transition)

    def __len__(self):
        """ number of sub-states """
        return len(self.sub_states)

    def __iter__(self):
        yield from self.sub_states

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
        if isinstance(key, int):
            return list(self.sub_states.values())[key]
        elif isinstance(key, str):
            return self.sub_states[key]
        elif isinstance(key, Path):
            return key.get_in(self)
        elif isinstance(key, tuple) and len(key) == 2:
            getter = lambda p: p.get_in(self)
            old_paths = get_extended_paths(key[0], getter=getter)
            new_paths = get_extended_paths(key[1], getter=getter)
            transitions = []
            for old_path in old_paths:
                for new_path in new_paths:
                    common, old_tail, new_tail = get_spliced_path(old_path, new_path)
                    transitions.extend(common.get_in(self).trans_dict[old_tail, new_tail])
            if not len(transitions):
                raise KeyError(f"key '{key}' does not exist in state {self.name}")
            return transitions
        raise KeyError(f"key '{key}' does not exist in state {self.name}")

    @lazy_property
    def triggers(self):
        """ gets a set of all trigger names in the state machine and all sub states recursively """
        triggers = set(t[1] for t in self.triggering)
        for state in self.sub_states.values():
            triggers.update(state.triggers)
        return triggers

    @lazy_property
    def default_path(self):
        """ returns the path to the default state the object will be in, when not specified """
        state = self
        path_list = []
        while len(state):
            state = state[0]
            path_list.append(state.name)
        return Path(path_list)

    @lazy_property
    def on_stays(self):
        return [state.callbacks.on_stay for state in self.up]

    def as_json_dict(self):
        jd = lambda v: v.as_json_dict()
        result = dict(name=self.name)
        if len(self):
            result['states'] = {n: jd(s) for n, s in self.sub_states.items()}
            result['transitions'] = [jd(t) for ts in self.trans_dict.values() for t in ts]
        result.update(jd(self.callbacks))
        if len(self.info):
            result['info'] = self.info
        return result

    def __str__(self):
        return str(self.path)

    def __repr__(self):
        return json.dumps(self.as_json_dict(), indent=4)


class State(BaseState):
    pass


class StateMachine(BaseState):
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

    @classmethod
    def from_config(cls, states, transitions=(), **config):
        if not len(transitions):
            transitions = []
            for old_state in states:
                for new_state in states:
                    transitions.append(dict(old_state=old_state, new_state=new_state, trigger='goto_' + new_state))
        config = standardize_statemachine_config(states=states,
                                                 transitions=transitions,
                                                 **config)
        return cls(**config)

    def __init__(self, states=None, transitions=(), **kwargs):
        """
        Constructor of the state machine, used to define all properties of the machine.
        :param states: a as_json_dict {name: {prop_name: property}} of state properties:
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
        super(StateMachine, self).__init__(states=states or {}, transitions=transitions, **kwargs)
        self._trigger_transitions = {}  # cache for transition lookup when trigger is called
        self.dict_key = None

    def __set_name__(self, cls, name):
        self.name = self._validate_name(name)
        self.dict_key = '_' + self.name

    def __get__(self, obj, cls=None):
        if obj is None:
            return self
        return str(obj.__dict__[self.dict_key])

    def __set__(self, obj, state_name):
        if self.dict_key in obj.__dict__:
            raise AttributeError(f"state {self.name} of {type(obj).__name__} cannot be changed directly; use triggers instead")
        obj.__dict__[self.dict_key] = Path(state_name)

    def set_state(self, obj, state):
        path = Path(state)
        try:
            target_state = path.get_in(self)
        except KeyError:
            raise TransitionError(f"state machine does not have a state '{state}'")
        else:
            setattr(obj, self.dict_key, path + target_state.default_path)

    def get_path(self, obj):
        return obj.__dict__[self.dict_key]

    def _get_states(self, *state_names):
        state_paths = get_expanded_paths(*state_names,
                                         getter=lambda p: self[p])
        return [path.get_in(self) for path in state_paths]

    def _get_transitions(self, old_state_name, new_state_name, check_length=False):
        spliced_paths = get_spliced_paths(old_state_name, new_state_name,
                                          getter=lambda p: self[p])

        transitions = []
        for common, old_tail, new_tail in spliced_paths:
            transitions.extend(common.get_in(self).trans_dict.get((old_tail, new_tail), ()))

        if check_length and not len(transitions):
            raise MachineError(f"no transitions found from '{old_state_name}' to '{new_state_name}'")
        return transitions

    def _register_state_callback(self, key, *state_names):
        states = list(self._get_states(*state_names))

        def register(func):
            for state in states:
                state.callbacks.register(key, func)
            return func

        return register

    def _register_transition_callback(self, key, old_state_name, new_state_name):
        transitions = self._get_transitions(old_state_name, new_state_name, check_length=True)

        def register(func):
            for transition in transitions:
                transition.callbacks.register(key, func)
            return func

        return register

    def on_entry(self, state_name, *state_names):
        return self._register_state_callback('on_entry', state_name, *state_names)

    def on_exit(self, state_name, *state_names):
        return self._register_state_callback('on_exit', state_name, *state_names)

    def on_stay(self, *state_names):
        return self._register_state_callback('on_stay', *state_names)

    def on_transfer(self, old_state_name, new_state_name):
        return self._register_transition_callback('on_transfer', old_state_name, new_state_name)

    def condition(self, old_state_name, new_state_name):
        transitions = self._get_transitions(old_state_name, new_state_name, check_length=True)

        def register(func):
            for transition in transitions:
                transition.add_condition(func)
            return func

        return register

    def initial_entry(self, obj, *args, **kwargs):
        for state in self.get_path(obj).iter_in(self):
            state.callbacks.on_entry(obj, *args, **kwargs)

    def _get_trigger_transitions(self, path, trigger):
        try:
            return self._trigger_transitions[path, trigger]
        except KeyError:
            for _, state, tail in path.trace_in(self, last=False):
                transitions = state.triggering.get((tail, trigger))
                if transitions:
                    self._trigger_transitions[path, trigger] = transitions
                    return transitions
            raise TransitionError(f"transition from '{str(path)}' with trigger '{trigger}' does not exist in '{self.name}'")

    def trigger(self, trigger, obj, *args, **kwargs):
        """ Executes the transition when called through a trigger """
        for transition in self._get_trigger_transitions(self.get_path(obj), trigger):
            if transition.condition(obj, *args, **kwargs):
                return transition.execute(obj, *args, **kwargs)
        raise TransitionError(f"error for transitions from '{obj.state}' with trigger '{trigger}': no default transition found")



state_machine = StateMachine.from_config

if __name__ == '__main__':
    pass

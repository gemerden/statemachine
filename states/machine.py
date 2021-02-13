import contextlib
import json
from collections import defaultdict
from functools import partial
from typing import Mapping

from .exception import MachineError, TransitionError
from .callbacks import Callbacks
from .transitions import Transition
from .normalize import normalize_statemachine_config, get_expanded_paths
from .tools import Path, lazy_property, dummy_context_manager, DummyMapping

_marker = object()


class BaseState(object):
    path = root = up = None

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

    def __init__(self, name=None, info="", on_stay=(), **callbacks):
        self.name = self._validate_name(name)
        self.callbacks = Callbacks(on_stay=on_stay, **callbacks)
        self.info = info

    @lazy_property
    def default_path(self):
        """ returns the path to the default state the object will be in, when not specified """
        state = self
        path_list = []
        while isinstance(state, ParentState):
            state = state[0]
            path_list.append(state.name)
        return Path(path_list)

    @lazy_property
    def default_state(self):
        return self.default_path.get_in(self)

    @lazy_property
    def on_stays(self):
        return [state.callbacks.on_stay for state in self.up]

    def as_json_dict(self, **extra):
        result = dict(name=self.name, **self.callbacks.as_json_dict())
        if len(self.info):
            result['info'] = self.info
        result.update(extra)
        return result

    def __str__(self):
        return f"State('{self.path}')"

    def __repr__(self):
        return json.dumps(self.as_json_dict(), indent=4)


class ParentState(BaseState, Mapping):
    def __init__(self, states, transitions, **kwargs):
        super().__init__(**kwargs)
        self._init_states(states)
        self._init_transitions(transitions)

    def _init_states(self, states):
        """creates a dictionary of state_name: BaseState key value pairs"""
        self.sub_states = {}
        for name, config in states.items():
            config.update(name=name, parent=self)
            if 'states' in config:
                self.sub_states[name] = NestedState(**config)
            else:
                self.sub_states[name] = LeafState(**config)

    def _init_transitions(self, transition_dicts):
        for trans_dict in transition_dicts:
            old_path = Path(trans_dict.pop('old_state'))
            old_path.get_in(self).create_transition(**trans_dict)

    def __len__(self):
        """ number of sub-states """
        return len(self.sub_states)

    def __iter__(self):
        yield from self.sub_states

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
        elif isinstance(key, tuple):
            if len(key) == 2:
                return Path(key[0]).get_in(self).transitions[key[1]]
            elif len(key) == 3:
                return Path(key[0]).get_in(self).transitions[key[1]][self.path + key[2]]
        raise KeyError(f"key '{key}' does not exist in state {self.name}")

    def iter_transitions(self):
        for state in self.sub_states.values():
            yield from state.iter_transitions()

    @lazy_property
    def triggers(self):
        """ gets a set of all trigger names in the state machine and its sub-states """
        return set.union(*(s.triggers for s in self.sub_states.values()))

    def lookup(self, path):
        for state in self.up:
            try:
                return path.get_in(state)
            except KeyError:
                pass
        raise MachineError(f"path '{path}' could not be found from state '{self.name}'")

    def as_json_dict(self, **extra):
        return super().as_json_dict(states={n: s.as_json_dict() for n, s in self.sub_states.items()}, **extra)


class ChildState(BaseState):
    def __init__(self, parent, on_entry=(), on_exit=(), **kwargs):
        super().__init__(on_entry=on_entry, on_exit=on_exit, **kwargs)
        self.parent = parent
        self.path = parent.path + self.name
        self.root = parent.root
        self.up = [self] + parent.up


class NestedState(ParentState, ChildState):
    pass


class LeafState(ChildState, DummyMapping):
    def __init__(self, transitions=(), **kwargs):
        super().__init__(**kwargs)
        self._init_transitions(transitions)

    def _init_transitions(self, transition_dicts):
        """creates a dictionary of (old state name, new state name): Transition key value pairs"""
        self.transitions = defaultdict(dict)
        for trans_dict in transition_dicts:
            target_name = trans_dict.pop('new_state')
            target = Path(target_name).get_in(self.root)
            self.create_transition(target=target, **trans_dict)

    def create_transition(self, **trans_dict):
        target = self.parent.lookup(Path(trans_dict.pop('new_state')))
        transition = Transition(state=self, target=target, **trans_dict)
        self.transitions[transition.trigger][transition.target_path] = transition

    def iter_transitions(self):
        for transition_dict in self.transitions.values():
            yield from transition_dict.values()

    @lazy_property
    def triggers(self):
        return set(self.transitions)

    def as_json_dict(self, **extra):
        return super().as_json_dict(transitions=[t.as_json_dict() for t in self.iter_transitions()], **extra)


class StateMachine(ParentState):

    @classmethod
    def from_config(cls, states, transitions=(), **config):
        if not len(transitions):
            transitions = []
            for old_state in states:
                for new_state in states:
                    transitions.append(dict(old_state=old_state, new_state=new_state, trigger='goto_' + new_state))
        config = normalize_statemachine_config(states=states, transitions=transitions, **config)
        return cls(**config)

    def __init__(self, states=None, transitions=(), on_stay=(), prepare=(), contextmanager=None, info=""):
        self.path = Path()
        self.root = self
        self.up = [self]
        super().__init__(states=states or {}, transitions=transitions,
                         on_stay=on_stay, prepare=prepare, info=info)
        self._contextmanager = contextmanager or dummy_context_manager(_marker)
        self._trigger_transitions_cache = {}  # cache for transition lookup when trigger is called
        self.attr_name = None

    def __set_name__(self, cls, name):
        self.name = self._validate_name(name)
        self.attr_name = '_' + self.name
        if cls._state_machines is None:
            cls._state_machines = {}
        cls._state_machines[self.name] = self
        self._install_triggers(cls)

    def _install_triggers(self, cls):
        trigger_functions = defaultdict(list)
        for machine in cls._state_machines.values():
            for trigger in machine.triggers:  # the names
                function = partial(machine.trigger, trigger)
                trigger_functions[trigger].append(function)

        for trigger, functions in trigger_functions.items():

            def trigger_function(self, *args, __functions=functions, **kwargs):
                for f in __functions:
                    f(self, *args, **kwargs)
                return self

            setattr(cls, trigger, trigger_function)

    def __get__(self, obj, cls=None):
        if obj is None:
            return self
        return getattr(obj, self.attr_name)

    def __set__(self, obj, state_name):
        """
         - store string version instead of Path() due to e.g. easier persistence in database
         - using setattr() instead of putting in __dict__ to enable external machinery of getattr to still be called
        """
        if hasattr(obj, self.attr_name):
            raise AttributeError(f"state {self.name} of {type(obj).__name__} cannot be changed directly; use triggers instead")
        setattr(obj, self.attr_name, state_name)

    def set_state(self, obj, state_name):
        path = Path(state_name)
        try:
            target_state = path.get_in(self)
        except KeyError:
            raise TransitionError(f"state machine does not have a state '{state_name}'")
        else:
            setattr(obj, self.attr_name, str(path + target_state.default_path))

    def get_path(self, obj):
        return Path(getattr(obj, self.attr_name))

    def _lookup_states(self, *state_names):
        state_paths = get_expanded_paths(*state_names,
                                         getter=lambda p: self[p])
        return [path.get_in(self) for path in state_paths]

    def _lookup_transitions(self, old_state_name_s, new_state_name_s, trigger=None):
        transitions = []
        getter = lambda p: self[p]
        for old_path in get_expanded_paths(old_state_name_s, getter=getter, extend=True):
            trans_dict = old_path.get_in(self).transitions
            triggers = [trigger] if trigger else list(trans_dict)
            for new_path in get_expanded_paths(new_state_name_s, getter=getter, extend=True):
                for trigg in triggers:
                    transition = trans_dict[trigg].get(new_path)
                    if transition is not None:
                        transitions.append(transition)
        return transitions

    def _register_state_callback(self, key, *state_names):
        states = self._lookup_states(*state_names)

        def register(func):
            for state in states:
                state.callbacks.register(key, func)
            return func

        return register

    def _register_transition_callback(self, key, old_state_name_s, new_state_name_s, trigger):
        transitions = self._lookup_transitions(old_state_name_s, new_state_name_s, trigger=trigger)

        if not len(transitions):
            raise MachineError(f"no transitions found from '{old_state_name_s}' to '{new_state_name_s}'")

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

    def on_transfer(self, old_state_name_s, new_state_name_s, trigger=None):
        return self._register_transition_callback('on_transfer', old_state_name_s, new_state_name_s, trigger)

    def condition(self, old_state_name_s, new_state_name_s, trigger=None):
        transitions = self._lookup_transitions(old_state_name_s, new_state_name_s, trigger)
        if len(transitions) != 1:
            raise MachineError(f"{len(transitions)} transition(s) found "
                               f"from '{old_state_name_s}' to '{new_state_name_s}' with '{trigger}' trigger")

        self._trigger_transitions_cache.clear()  # a condition can result in a new default transition being created

        def register(func):
            transitions[0].add_condition(func)
            return func

        return register

    def prepare(self, func):
        self.callbacks.register('prepare', func)

    def contextmanager(self, func):
        self._contextmanager = contextlib.contextmanager(func)

    def init_entry(self, obj, *args, **kwargs):
        for state in self.get_path(obj).iter_in(self):
            state.callbacks.on_entry(obj, *args, **kwargs)

    def _get_trigger_transitions(self, state_name, trigger):
        try:
            return self._trigger_transitions_cache[state_name, trigger]
        except KeyError:
            transitions = list(Path(state_name).get_in(self).transitions[trigger].values())
            if transitions:
                self._trigger_transitions_cache[state_name, trigger] = transitions
                return transitions
            raise TransitionError(f"transition from '{state_name}' with trigger '{trigger}' does not exist in '{self.name}'")

    def trigger(self, trigger, obj, *args, **kwargs):
        """ Executes the transition when called through a trigger """
        self.callbacks.prepare(obj, *args, **kwargs)
        with self._contextmanager(obj, *args, **kwargs) as context:
            if context is not _marker:
                if 'context' in kwargs:
                    raise TransitionError(f"cannot pass context from contextmanager: trigger called with argument 'context'")
                kwargs['context'] = context
            for transition in self._get_trigger_transitions(getattr(obj, self.attr_name), trigger):
                if transition.condition(obj, *args, **kwargs):
                    return transition.execute(obj, *args, **kwargs)
            raise TransitionError(f"no transitions from '{obj.state}' with trigger '{trigger}' found")

    def __str__(self):
        return f"StateMachine('{self.name}')"


state_machine = StateMachine.from_config

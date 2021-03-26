import contextlib
import json
from collections import defaultdict
from itertools import product
from operator import attrgetter, itemgetter
from typing import Mapping

from .exception import MachineError, TransitionError
from .callbacks import Callbacks
from .transitions import Transition
from .normalize import normalize_statemachine_config, get_expanded_paths
from .tools import Path, lazy_property, DummyMapping, save_graph, group_by, listify

_marker = object()


class BaseState(object):
    parent = path = root = up = None

    @classmethod
    def _validate_name(cls, name, exclude=(".", "*", "[", "]", "(", ")"), underscore=True):
        if name is None:
            return None
        if not len(name.strip()):
            raise MachineError(f"state or state machine must have a name")
        if not underscore and name.startswith('_'):
            raise MachineError(f"state or machine name '{name}' cannot start with an '_'")
        if any(c in name for c in exclude):
            raise MachineError(f"state or machine name '{name}' cannot contain characters %s" % exclude)
        return name

    def __init__(self, name=None, info="", on_stay=(), constraint=(), **callbacks):
        self.callbacks = Callbacks(on_stay=on_stay, constraint=constraint, **callbacks)
        self.name = self._validate_name(name)
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

    def validate_transitions(self):
        pass

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
    def __init__(self, states, before_exit=(), after_entry=(), **kwargs):
        super().__init__(before_exit=before_exit, after_entry=after_entry, **kwargs)
        self._init_states(states)

    def _init_states(self, states):
        """creates a dictionary of state_name: BaseState key value pairs"""
        self.sub_states = {}
        for name, config in states.items():
            config.update(name=name, parent=self)
            if 'states' in config:
                self.sub_states[name] = NestedState(**config)
            else:
                self.sub_states[name] = LeafState(**config)

    def _init_transitions(self):
        for state in self.values():
            state._init_transitions()

    def __len__(self):
        """ number of sub-states """
        return len(self.sub_states)

    def __iter__(self):
        yield from self.sub_states

    def __getitem__(self, key):
        """
        Gets sub states according to string key or Path()
        """
        if isinstance(key, int):
            return list(self.sub_states.values())[key]
        elif isinstance(key, str):
            return self.sub_states[key]
        elif isinstance(key, Path):
            return key.get_in(self)
        raise KeyError(f"key '{key}' does not exist in state {self.name}")

    def iter_states(self, key=lambda s: True):
        if key(self):
            yield self
        for state in self.sub_states.values():
            yield from state.iter_states(key)

    def iter_transitions(self, key=lambda t: True):
        for state in self.sub_states.values():
            yield from state.iter_transitions(key)

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

    def validate_transitions(self):
        super().validate_transitions()
        for state in self.sub_states.values():
            state.validate_transitions()

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
        self._trans_configs = transitions  # temp; cannot create transitions before state-tree is finished

    def _init_transitions(self):
        """creates a dictionary of (old state name, new state name): Transition key value pairs"""
        self.trigger_transitions = defaultdict(list)
        for trans_dict in self._trans_configs:
            del trans_dict['old_state']  # we are already there
            target_names = trans_dict.pop('new_state')
            targets = [Path(n).get_in(self.root) for n in target_names]
            self.create_transition(targets, **trans_dict)
        del self._trans_configs

    def create_transition(self, targets, **trans_dict):
        transition = Transition(self, *targets, **trans_dict)
        self.trigger_transitions[transition.trigger].append(transition)
        self.update_transitions(transition.trigger)

    def update_transitions(self, trigger):
        """ keep the transitions without condition (potential default) last """
        self.trigger_transitions[trigger].sort(key=lambda t: not t.callbacks.get('condition'))

    def iter_states(self, key=lambda s: True):
        if key(self):
            yield self

    def iter_transitions(self, key=lambda t: True):
        for transitions in self.trigger_transitions.values():
            for transition in transitions:
                if key(transition):
                    yield transition

    @lazy_property
    def triggers(self):
        return set(self.trigger_transitions)

    def validate_transitions(self):
        for trigger in self.trigger_transitions:
            self.update_transitions(trigger)
            transitions = self.trigger_transitions[trigger]
            for transition in transitions[:-1]:
                if not transition.conditions:
                    raise MachineError(f"missing condition in transition {str(transition)} in machine '{self.name}'")
            if transitions[-1].conditions:
                if any(t.is_same_state for t in transitions):
                    raise MachineError(f"default transition for conditional transitions from '{str(self.path)}' "
                                       f"with trigger '{trigger}' cannot be created, same state transition "
                                       f"already exists in machine '{self.name}'")
                transitions.append(Transition(self, trigger=trigger,
                                              info="auto-generated default transition"))

    def as_json_dict(self, **extra):
        return super().as_json_dict(transitions=[t.as_json_dict() for t in self.iter_transitions()], **extra)


class StateMachine(ParentState):

    @classmethod
    def from_config(cls, name=None, states=None, transitions=(), **config):
        if not states:
            raise MachineError(f"cannot initialize state-machine without states")
        if not len(transitions):
            transitions = []
            for old_state in states:
                for new_state in states:
                    transitions.append(dict(old_state=old_state, new_state=[new_state], trigger='goto_' + new_state))
        normalized_config = normalize_statemachine_config(states=states, transitions=transitions, **config)
        return cls(name=name, **normalized_config)

    def __init__(self, name=None, states=None, on_stay=(), prepare=(), contextmanager=(), info=""):
        self.path = Path()
        self.root = self
        self.up = [self]
        super().__init__(name=name, states=states or {}, on_stay=on_stay,
                         prepare=prepare, contextmanager=contextmanager, info=info)
        self._init_transitions()
        self._callback_cache = defaultdict(dict)  # cache for transition lookup when trigger is called
        self.use_attr = False
        self.owner_cls = None
        self.validated = False

    def _reset_on_new_callback(self):
        self._callback_cache.clear()
        if self.owner_cls:
            self.install_triggers(self.owner_cls)

    def __set_name__(self, cls, name):
        self.owner_cls = cls
        if not cls._state_machines:
            cls._state_machines = []
        cls._state_machines.append(self)

        if self.name and self.name != name:
            self.use_attr = True
        else:
            self.name = self._validate_name(name)

    def __get__(self, obj, cls=None):
        if obj is None:
            return self
        if self.use_attr:
            return getattr(obj, self.name)
        else:
            return obj.__dict__[self.name]

    def __set__(self, obj, state_name):
        """
         - store string version instead of Path() due to e.g. easier persistence in database
         - using setattr() instead of putting in __dict__ to enable external machinery of setattr to still be called
        """
        if (self.use_attr and getattr(obj, self.name, None)) or self.name in obj.__dict__:
            raise TransitionError(f"state of {type(obj).__name__} cannot be changed directly; use triggers instead")

        path = Path(state_name)
        try:
            target = path.get_in(self)
        except KeyError:
            raise TransitionError(f"state machine does not have a state '{state_name}'")
        else:
            full_state_name = str(path + target.default_path)
            if self.use_attr:
                setattr(obj, self.name, full_state_name)
            else:
                obj.__dict__[self.name] = full_state_name

    def set_state_callback(self, state_name):
        name = self.name
        if self.use_attr:
            def inner_set_state_callback(obj, *_, **__):  # mimic other callbacks
                setattr(obj, name, state_name)
        else:
            def inner_set_state_callback(obj, *_, **__):
                obj.__dict__[name] = state_name

        return inner_set_state_callback

    def set_from_kwargs(self, obj, kwargs):
        state_name = kwargs.pop(self.name, '')
        self.__set__(obj, state_name)

    def install_triggers(self, cls):
        """
        Adds trigger methods to the owner class, the trigger method can trigger multiple state machines

        :param cls: owner class on which the triggers are installed
        """
        trigger_functions = defaultdict(list)
        for machine in cls._state_machines:  # gather state machines organized by trigger (name)
            for trigger_name in machine.triggers:
                trigger_function = machine.get_trigger(trigger_name)
                trigger_functions[trigger_name].append(trigger_function)

        for trigger_name, funcs in trigger_functions.items():
            if len(funcs) == 1:
                trigger_function = funcs[0]
            else:
                def trigger_function(obj, *args, __fs=funcs, **kwargs):
                    for f in __fs:  # one f per state machine
                        f(obj, *args, **kwargs)
                    return obj

            trigger_function.__name__ = trigger_name
            setattr(cls, trigger_name, trigger_function)

    def resolve_callbacks(self, cls):
        """
            looks up callbacks defined with strings on the class. Called in __set_name__, when cls is known.
            Callbacks that are added later are already callables, because they are added by decoration.
        """
        try:
            for state in self.iter_states():
                state.callbacks.resolve(cls)
            for transition in self.iter_transitions():
                transition.callbacks.resolve(cls)
        except AttributeError as error:
            raise MachineError(f"callback lookup failed: {str(error)}")

    def _lookup_states(self, *state_names):
        state_paths = get_expanded_paths(*state_names,
                                         getter=lambda p: self[p])
        return [path.get_in(self) for path in state_paths]

    def _lookup_transitions(self, *state_name_s, trigger=None):

        def get_paths(names):
            return get_expanded_paths(*listify(names), getter=lambda p: self[p], extend=True)

        all_paths = [get_paths(ns) for ns in state_name_s]

        transitions = []
        for transition in self.iter_transitions():
            for paths in product(*all_paths):
                if transition.match(*paths, trigger=trigger):
                    transitions.append(transition)

        if not len(transitions):
            raise MachineError(
                f"no transitions found over '{state_name_s}' with trigger '{trigger}'")
        return transitions

    def _register_state_callback(self, key, *state_names):
        state_names = state_names or ("",)
        states = self._lookup_states(*state_names)

        def register(func):
            for state in states:
                state.callbacks.register(**{key: func})
            return func

        self._reset_on_new_callback()
        return register

    @property
    def states(self):
        return [s.name for s in self.iter_states() if s is not self]

    @property
    def transitions(self):
        return [tuple(map(str, (s.path for s in t.states))) for t in self.iter_transitions()]

    def on_entry(self, state_name, *state_names):
        return self._register_state_callback('on_entry', state_name, *state_names)

    def on_exit(self, state_name, *state_names):
        return self._register_state_callback('on_exit', state_name, *state_names)

    def on_stay(self, *state_names):
        return self._register_state_callback('on_stay', *state_names)

    def before_exit(self, *state_names):
        return self._register_state_callback('before_exit', *state_names)

    def after_entry(self, *state_names):
        return self._register_state_callback('after_entry', *state_names)

    def constraint(self, *state_names):
        if self.validated:
            raise MachineError(f"cannot dynamically add constraint for {state_names} "
                               f"to '{self.name}' after class construction")
        return self._register_state_callback('constraint', *state_names)

    def on_transfer(self, *state_name_s, trigger=None):
        transitions = self._lookup_transitions(*state_name_s, trigger=trigger)

        def register(func):
            for transition in transitions:
                transition.callbacks.register(on_transfer=func)
            return func

        self._reset_on_new_callback()
        return register

    def condition(self, *state_name_s, trigger=None):
        if self.validated:
            raise MachineError(f"cannot dynamically add condition in '{self.name}' after class construction")
        all_transitions = self._lookup_transitions(*state_name_s, trigger=trigger)
        grouped_transitions = group_by(all_transitions, key=lambda t: str(t.states[0].path))  # old_state
        for old_state_name, transitions in grouped_transitions.items():
            if len(transitions) > 1:
                raise MachineError(f"multiple transition(s) found when setting condition for transition "
                                   f"over '{state_name_s}' with '{trigger}' trigger")

        def register(func):
            for transitions in grouped_transitions.values():
                transitions[0].add_condition(func)
            return func

        self._reset_on_new_callback()
        return register

    def prepare(self, func):
        self.callbacks.register(prepare=func)
        self._reset_on_new_callback()
        return func

    def contextmanager(self, keyword=None):
        if keyword:
            for ctx_mgr in self.callbacks['contextmanager']:
                if ctx_mgr.__keyword__ == keyword:
                    raise MachineError(f"contextmanager with keyword '{keyword}' already exists")

        def register(gen):
            ctx_manager = contextlib.contextmanager(gen)
            ctx_manager.__keyword__ = keyword
            self.callbacks.register(contextmanager=ctx_manager)

        self._reset_on_new_callback()
        return register

    def _get_contextmanager(self):
        ctx_mgrs = self.callbacks['contextmanager']
        if not ctx_mgrs:
            return None

        if len(ctx_mgrs) == 1:
            context_manager = ctx_mgrs[0]
            keyword = context_manager.__keyword__

            def create_context(obj, *args, **kwargs):
                with context_manager(obj, *args, **kwargs) as context:
                    yield {keyword: context} if keyword else None
        else:
            keywords = [c.__keyword__ for c in ctx_mgrs]

            def create_context(obj, *args, **kwargs):
                with contextlib.ExitStack() as stack:
                    enter = stack.enter_context
                    contexts = [enter(cm(obj, *args, **kwargs)) for cm in ctx_mgrs]
                    yield {kw: ctx for kw, ctx in zip(keywords, contexts) if kw}

        return contextlib.contextmanager(create_context)

    def init_entry(self, obj, *args, **kwargs):
        """
        entry in initial state, optional during object construction;
        somewhat laborious since no convenient transition exists
        """
        if self.callbacks.prepare:
            self.callbacks.prepare(obj, *args, **kwargs)

        ctx_mgr = self._get_contextmanager()
        if ctx_mgr:
            with ctx_mgr(obj, *args, **kwargs) as context:
                for state in Path(getattr(obj, self.name)).iter_in(self):
                    state.callbacks.on_entry(obj, *args, **context, **kwargs)
                    state.parent.callbacks.after_entry(obj, *args, **context, **kwargs)
        else:
            for state in Path(getattr(obj, self.name)).iter_in(self):
                state.callbacks.on_entry(obj, *args, **kwargs)
                state.parent.callbacks.after_entry(obj, *args, **kwargs)

    def get_trigger(self, trigger):
        """ returns the function that executes when a trigger is called """
        callback_cache = self._callback_cache[trigger]
        attr_name = self.name
        use_attr = self.use_attr

        def get_callbacks(state_name):
            transactions = Path(state_name).get_in(self).trigger_transitions[trigger]
            if transactions:
                return [(t.conditions or None, t.effective_callbacks) for t in transactions]  # resolve falsehood
            raise TransitionError(f"no transition from '{state_name}' with trigger '{trigger}' in machine '{self.name}'")

        def execute(obj, *args, **kwargs):
            if use_attr:
                state_name = getattr(obj, attr_name)
            else:
                state_name = obj.__dict__[attr_name]
            try:
                condition_callbacks = callback_cache[state_name]
            except KeyError:
                condition_callbacks = callback_cache[state_name] = get_callbacks(state_name)

            for conditions, callbacks in condition_callbacks:
                if conditions is None or all(c(obj, *args, **kwargs) for c in conditions):
                    for callback in callbacks:
                        callback(obj, *args, **kwargs)
                    return obj
            raise MachineError(f"no transition returned 'True' from '{obj.state}' with trigger '{trigger}'; please report!")

        def get_trigger_func(execute_, prepare_, contextmanager_):
            if contextmanager_:
                if prepare_:
                    def trigger_func(obj, *args, **kwargs):
                        prepare_(obj, *args, **kwargs)
                        with contextmanager_(obj, *args, **kwargs) as context:
                            return execute_(obj, *args, **context, **kwargs)
                else:
                    def trigger_func(obj, *args, **kwargs):
                        with contextmanager_(obj, *args, **kwargs) as context:
                            return execute_(obj, *args, **context, **kwargs)
            else:
                if prepare_:
                    def trigger_func(obj, *args, **kwargs):
                        prepare_(obj, *args, **kwargs)
                        return execute_(obj, *args, **kwargs)
                else:
                    trigger_func = execute_

            return trigger_func

        return get_trigger_func(execute, self.callbacks.prepare, self._get_contextmanager())

    def validate_transitions(self):
        super().validate_transitions()
        self.validated = True

    def save_graph(self, filename, view=False, fontsize='10', fontname='Arial bold', **options):
        save_graph(machine=self,
                   view=view,
                   filename=filename,
                   fontsize=fontsize,
                   fontname=fontname,
                   **options)

    def __str__(self):
        return f"StateMachine('{self.name}')"


state_machine = StateMachine.from_config

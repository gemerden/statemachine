__author__ = "lars van gemerden"

import json
from itertools import zip_longest

from .callbacks import Callbacks
from .tools import Path, lazy_property


class Transition(object):
    """class for the internal representation of transitions in the state machine"""

    def __init__(self, state, *states, trigger,
                 on_transfer=(), condition=(), info=""):
        self.callbacks = Callbacks(on_transfer=on_transfer,
                                   condition=condition)
        self.states = [state] + list(states)
        self.trigger = trigger
        self.info = info

    @lazy_property
    def is_same_state(self):
        return len(self.states) == 1

    @lazy_property
    def root(self):
        return self.states[0].root

    def common_state(self, *states):
        states = states or self.states
        common_path, *_ = Path.splice(*(s.path for s in states))
        return common_path.get_in(self.root)

    @property
    def conditions(self):
        conditions = self.callbacks['condition']
        for target in self.states[1:]:
            for state in target.up:
                conditions.extend(state.callbacks['constraint'])
        return [c for c in conditions if c]

    @property
    def on_transfers(self):
        return self.callbacks['on_transfer']

    @property
    def before_exits(self):
        if self.is_same_state:
            return []
        all_exits = sum((s.parent.callbacks['before_exit'] for s in self.states[0].up if s.parent), [])
        return list(reversed([e for e in all_exits if e]))

    @property
    def after_entries(self):
        if self.is_same_state:
            return []
        all_entries = sum((s.parent.callbacks['after_entry'] for s in self.states[-1].up if s.parent), [])
        return [e for e in all_entries if e]

    def on_exits(self, old_state, new_state):
        on_exits = self.before_exits
        common_state = self.common_state(old_state,
                                         new_state)
        for state in old_state.up:
            if state is common_state:
                break
            on_exits.extend(state.callbacks['on_exit'])
        return [e for e in on_exits if e]

    def on_entries(self, old_state, new_state):
        on_entries = []
        common_state = self.common_state(old_state,
                                         new_state)
        for state in new_state.up:
            if state is common_state:
                break
            on_entries.extend(state.callbacks['on_entry'])
        return list(reversed([e for e in on_entries if e])) + self.after_entries

    @property
    def on_stays(self):
        return sum((s.callbacks['on_stay'] for s in self.common_state().up if s.callbacks['on_stay']), [])

    def set_state(self, state):
        return self.root.set_state_callback(str(state.path))

    @property
    def effective_callbacks(self):
        callbacks = []
        for old_state, new_state in zip(self.states, self.states[1:]):
            callbacks.extend([*self.on_exits(old_state, new_state),
                              self.set_state(new_state),
                              *self.on_entries(old_state, new_state)])
        callbacks.extend(self.on_transfers)
        callbacks.extend(self.on_stays)
        return callbacks

    @property
    def execute(self):
        conditions = self.conditions
        callbacks = self.effective_callbacks

        if conditions:
            def execute(obj, *args, **kwargs):
                if any(c(obj, *args, **kwargs) for c in conditions):
                    for callback in callbacks:
                        callback(obj, *args, **kwargs)
                    return True
                return False
        else:
            def execute(obj, *args, **kwargs):
                for callback in callbacks:
                    callback(obj, *args, **kwargs)
                return True

        return execute

    def add_condition(self, callback):
        self.callbacks.register(condition=callback)
        self.states[0].update_transitions(self.trigger)

    def match(self, *paths, trigger=None):
        if trigger and trigger != self.trigger:
            return False
        return all(p == getattr(s, 'path', None) for p, s in zip_longest(paths, self.states))

    def as_json_dict(self):
        result = dict(states=[str(s.path) for s in self.states],
                      trigger=self.trigger)
        result.update(self.callbacks.as_json_dict())
        if len(self.info):
            result['info'] = self.info
        return result

    def __str__(self):
        """ string representing the transition """
        return f"Transition({', '.join([str(s.path) for s in self.states])}, trigger={self.trigger})"

    def __repr__(self):
        return json.dumps(self.as_json_dict(), indent=4)

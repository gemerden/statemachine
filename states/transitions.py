__author__ = "lars van gemerden"

import json

from .callbacks import Callbacks
from .tools import Path, lazy_property


class Transition(object):
    """class for the internal representation of transitions in the state machine"""

    def __init__(self, state, target, trigger,
                 on_transfer=(), condition=(), info=""):
        self.callbacks = Callbacks(on_transfer=on_transfer,
                                   condition=condition)
        self.state = state
        self.target = target
        self.trigger = trigger
        self.info = info

    @lazy_property
    def common_state(self):
        common, _, _ = Path.splice(self.state.path,
                                   self.target.path)
        return common.get_in(self.state.root)

    @property
    def conditions(self):
        conditions = [*self.callbacks['condition']]
        for state in self.target.up:
            conditions.extend(state.callbacks['constraint'])
        return [c for c in conditions if c]

    @property
    def on_transfers(self):
        return self.callbacks['on_transfer']

    @property
    def on_exits(self):
        on_exits = []
        common = False
        for state in self.state.up:
            if state.parent:
                on_exits.extend(state.parent.callbacks['before_exit'])
            if state is self.common_state:
                common = True
            if not common:
                on_exits.extend(state.callbacks['on_exit'])
        return [e for e in on_exits if e]

    @property
    def on_entries(self):
        on_entries = []
        common = False
        for state in self.target.up:
            if state.parent:
                on_entries.extend(state.parent.callbacks['after_entry'])
            if state is self.common_state:
                common = True
            if not common:
                on_entries.extend(state.callbacks['on_entry'])
        return list(reversed([e for e in on_entries if e]))

    @property
    def inner_stays(self):
        return sum((s.callbacks['on_stay'] for s in self.state.up if s.callbacks['on_stay']), [])

    @property
    def outer_stays(self):
        return sum((s.callbacks['on_stay'] for s in self.common_state.up if s.callbacks['on_stay']), [])

    @property
    def set_state(self):
        return self.state.root.set_state_callback(str(self.target.path))

    @property
    def effective_callbacks(self):
        if self.state is self.target:
            return [*self.on_transfers,
                    *self.inner_stays]
        else:
            return [*self.on_exits,
                    self.set_state,
                    *self.on_transfers,
                    *self.outer_stays,
                    *self.on_entries]

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
        self.state.update_transitions(self.trigger)

    def as_json_dict(self):
        result = dict(old_state=str(self.state.path),
                      new_state=str(self.target.path),
                      trigger=self.trigger)
        result.update(self.callbacks.as_json_dict())
        if len(self.info):
            result['info'] = self.info
        return result

    def __str__(self):
        """ string representing the transition """
        return f"Transition({self.state.path}, {self.target.path}, trigger={self.trigger})"

    def __repr__(self):
        return json.dumps(self.as_json_dict(), indent=4)

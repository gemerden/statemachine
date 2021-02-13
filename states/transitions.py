__author__ = "lars van gemerden"

import json

from .callbacks import Callbacks
from .exception import MachineError
from .tools import Path, lazy_property


class Transition(object):
    """class for the internal representation of transitions in the state machine"""

    def __init__(self, state, target, trigger,
                 on_transfer=(), condition=(), info=""):
        """ after_transfer is from switched transition on_transfer specific for the new state """
        self.callbacks = Callbacks(on_transfer=on_transfer,
                                   condition=condition)
        self.state = state
        self.target = target
        self.trigger = trigger
        self.info = info
        self.state_path = self.state.path
        self.target_path = self.target.path
        self.condition = self.callbacks.condition

    @lazy_property
    def common_state(self):
        common, _, _ = Path.splice(self.state_path,
                                   self.target_path)
        return common.get_in(self.state.root)

    @lazy_property
    def on_exits(self):
        on_exits = []
        for state in self.state.up:
            if state is self.common_state:
                break
            on_exits.append(state.callbacks.on_exit)
        return on_exits

    @lazy_property
    def on_entries(self):
        on_entries = []
        for state in self.target.up:
            if state is self.common_state:
                break
            on_entries.append(state.callbacks.on_entry)
        return list(reversed(on_entries))

    @lazy_property
    def execute(self):
        target_name = str(self.target_path)
        on_exits = self.on_exits
        on_entries = self.on_entries
        on_transfer = self.callbacks.on_transfer
        inner_stays = self.state.on_stays
        outer_stays = self.common_state.on_stays
        set_state = self.state.root.set_state  # TODO: faster?

        if self.state is self.target:
            callbacks = [on_transfer] + inner_stays

            def execute(obj, *args, **kwargs):
                for callback in callbacks:
                    callback(obj, *args, **kwargs)
                return obj
        else:
            exit_callbacks = on_exits
            entry_callbacks = [on_transfer] + on_entries + outer_stays

            def execute(obj, *args, **kwargs):
                for callback in exit_callbacks:
                    callback(obj, *args, **kwargs)
                set_state(obj, target_name)
                for callback in entry_callbacks:
                    callback(obj, *args, **kwargs)
                return obj

        return execute

    def add_condition(self, condition_func):
        self.callbacks.register("condition", condition_func)
        related = list(self.state.transitions[self.trigger].values())
        if related[-1].callbacks.has_any("condition"):
            if any(t.state is t.target for t in related):
                raise MachineError(f"cannot create default same state transition from '{self.state.name}' "
                                   f"with trigger '{self.trigger}': same state transition already exists")
            else:
                self.state.create_transition(new_state=str(self.state_path), trigger=self.trigger,
                                             info="auto-generated default transition in case conditions fails")

    def as_json_dict(self):
        result = dict(old_state=str(self.state_path),
                      new_state=str(self.target_path),
                      trigger=self.trigger)
        result.update(self.callbacks.as_json_dict())
        if len(self.info):
            result['info'] = self.info
        return result

    def __str__(self):
        """ string representing the transition """
        return f"Transition({self.state_path}, {self.target_path}, trigger={self.trigger})"

    def __repr__(self):
        return json.dumps(self.as_json_dict(), indent=4)

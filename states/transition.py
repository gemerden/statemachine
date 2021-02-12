__author__ = "lars van gemerden"

import json

from .callbacks import Callbacks
from .exception import MachineError
from .tools import Path


class Transition(object):
    """class for the internal representation of transitions in the state machine"""

    @classmethod
    def _validate(cls, old_state, new_state):
        """ assures that no internal transitions are defined on an outer state level"""
        old_states = old_state.split(".", 1)
        new_states = new_state.split(".", 1)
        if (len(old_states) > 1 or len(new_states) > 1) and old_states[0] == new_states[0]:
            raise MachineError("inner transitions in a nested state machine cannot be defined at the outer level")

    def __init__(self, machine, old_state, new_state, trigger,
                 on_transfer=(), condition=(), info=""):
        """ after_transfer is from switched transition on_transfer specific for the new state """
        self._validate(old_state, new_state)
        self.callbacks = Callbacks(on_transfer=on_transfer,
                                   condition=condition)
        self.machine = machine
        self.trigger = trigger
        self.old_path = Path(old_state)
        self.new_path = Path(new_state)
        self.old_state = self.old_path.get_in(machine)
        self.new_state = self.new_path.get_in(machine)
        self.info = info
        self.condition = self.callbacks.condition
        self.execute = self.get_execute()

    def get_execute(self):
        new_state_name = str(self.machine.path + self.new_path)
        on_exits = [s.callbacks.on_exit for s in self.old_path.iter_out(self.machine)]
        on_entries = [s.callbacks.on_entry for s in self.new_path.iter_in(self.machine)]
        on_transfer = self.callbacks.on_transfer
        inner_stays = self.old_state.on_stays
        outer_stays = self.machine.on_stays
        set_state = self.machine.root.set_state

        if self.old_state is self.new_state:
            callbacks = [on_transfer] + inner_stays

            def execute(obj, *args, **kwargs):
                for callback in callbacks:
                    callback(obj, *args, **kwargs)
                return obj
        else:
            old_state_callbacks = on_exits
            new_state_callbacks = [on_transfer] + on_entries + outer_stays

            def execute(obj, *args, **kwargs):
                for callback in old_state_callbacks:
                    callback(obj, *args, **kwargs)
                set_state(obj, new_state_name)
                for callback in new_state_callbacks:
                    callback(obj, *args, **kwargs)
                return obj

        return execute

    def add_condition(self, condition_func):
        self.callbacks.register("condition", condition_func)
        related = self.machine.triggering[self.old_path, self.trigger]
        if related[-1].callbacks.has_any("condition"):
            if any(t.old_state is t.new_state for t in related):
                raise MachineError(f"cannot create default same state transition from '{self.old_state.name}' "
                                   f"with trigger '{self.trigger}': same state transition already exists")
            else:
                self.machine.create_transition(str(self.old_path), str(self.old_path), trigger=self.trigger,
                                               info="auto-generated default transition in case conditions fails")

    # def clean_copy(self, **overrides):
    #     """ clean -> no callbacks """
    #     kwargs = dict(machine=self.machine,
    #                   old_state=str(self.old_path),
    #                   new_state=str(self.new_path),
    #                   trigger=self.trigger,
    #                   info=self.info)
    #     kwargs.update(**overrides)
    #     return self.machine.create_transition(**kwargs)
    #
    # def default_copy(self):
    #     return self.clean_copy(new_state=str(self.old_path), info="auto-generated default transition in case conditions fail")
    #
    def as_json_dict(self):
        result = dict(old_state=str(self.old_state),
                      new_state=str(self.new_state),
                      trigger=self.trigger)
        result.update(self.callbacks.as_json_dict())
        if len(self.info):
            result['info'] = self.info
        return result

    def __str__(self):
        """ string representing the transition """
        return f"<{str(self.old_path)}, {str(self.new_path)}, trigger={self.trigger}>"

    def __repr__(self):
        return json.dumps(self.as_json_dict(), indent=4)

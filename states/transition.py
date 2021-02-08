__author__ = "lars van gemerden"

import json

from states.callbacks import Callbacks
from states.tools import MachineError, lazy_property, Path


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
        inner_stays = self.old_state.do_on_stays
        outer_stays = self.machine.do_on_stays
        set_state = self.machine.root.set_state

        if self.old_state is self.new_state:
            def execute(obj, *args, **kwargs):
                on_transfer(obj, *args, **kwargs)
                inner_stays(obj, *args, **kwargs)
        else:
            def execute(obj, *args, **kwargs):
                for on_exit in on_exits:
                    on_exit(obj, *args, **kwargs)
                set_state(obj, new_state_name)
                on_transfer(obj, *args, **kwargs)
                for on_entry in on_entries:
                    on_entry(obj, *args, **kwargs)
                outer_stays(obj, *args, **kwargs)
        return execute

    def add_condition(self, condition_func):
        self.callbacks.register("condition", condition_func)
        related = self.machine.triggering[self.old_path, self.trigger]
        if related[-1].callbacks.has_any("condition"):
            if any(t.old_state is t.new_state for t in related):
                raise MachineError(f"cannot create default same state transition from '{self.old_state.name}' "
                                   f"with trigger '{self.trigger}': same state transition already exists")
            else:
                self.machine.append_transition(self.default_copy())

    def clean_copy(self, **overrides):
        """ clean = no callbacks """
        kwargs = dict(machine=self.machine,
                      old_state=str(self.old_path),
                      new_state=str(self.new_path),
                      trigger=self.trigger,
                      info=self.info)
        kwargs.update(**overrides)
        return Transition(**kwargs)

    def default_copy(self):
        return self.clean_copy(new_state=str(self.old_path), on_transfer=(), info="default transition when conditions fail")

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


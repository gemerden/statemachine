__author__ = "lars van gemerden"

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
        self.callbacks = Callbacks(on_transfer=on_transfer, condition=condition)
        self._validate(old_state, new_state)
        self.machine = machine
        self.trigger = trigger
        self.old_path = Path(old_state)
        self.new_path = Path(new_state)
        self.old_state = self.old_path.get_in(machine)
        self.new_state = self.new_path.get_in(machine)
        self.new_state_name = str(self.machine.path + self.new_path)  # + self.new_path.get_in(self.machine).default_path
        self.info = info

    @lazy_property
    def obj_key(self):
        return self.machine.root.dict_key

    @lazy_property
    def on_exits(self):
        return [s.callbacks.on_exit for s in self.old_path.iter_out(self.machine)]

    @lazy_property
    def on_entries(self):
        return [s.callbacks.on_entry for s in self.new_path.iter_in(self.machine)]

    @lazy_property
    def on_transfer(self):
        return self.callbacks.on_transfer

    @lazy_property
    def condition(self):
        return self.callbacks.condition

    @lazy_property
    def on_stay(self):
        return self.old_state.callbacks.on_stay

    def execute(self, obj, *args, **kwargs):
        if self.condition(obj, *args, **kwargs):
            if self.old_state is self.new_state:
                self.on_transfer(obj, *args, **kwargs)
                self.on_stay(obj, *args, **kwargs)
            else:
                for on_exit in self.on_exits:
                    on_exit(obj, *args, **kwargs)
                setattr(obj, self.obj_key, self.new_state_name)
                self.on_transfer(obj, *args, **kwargs)
                for on_entry in self.on_entries:
                    on_entry(obj, *args, **kwargs)
            return True
        else:
            return False

    def add_condition(self, condition_func):
        self.callbacks.register("condition", condition_func)
        related = self.machine.triggering[self.old_path, self.trigger]
        if related[-1].callbacks.has_any("condition"):
            if any(t.old_state is t.new_state for t in related):
                raise MachineError(f"cannot create default same state transition from '{self.old_state.name}' "
                                   f"with trigger '{self.trigger}': same state transition already exists")
            else:
                self.machine.append_transition(self.clean_copy(new_state=str(self.old_path),
                                                               on_transfer=(),
                                                               info="default transition when conditions fail"))

    def clean_copy(self, **overrides):
        """ clean = no callbacks """
        kwargs = dict(machine=self.machine,
                      old_state=str(self.old_path),
                      new_state=str(self.new_path),
                      trigger=self.trigger,
                      info=self.info)
        kwargs.update(**overrides)
        return Transition(**kwargs)

    def __str__(self):
        """ string representing the transition """
        return f"<{str(self.old_path)}, {str(self.new_path)}, trigger={self.trigger}>"

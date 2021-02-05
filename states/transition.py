__author__ = "lars van gemerden"

from states.callbacks import Callbacks
from states.tools import MachineError, lazy_property, Path


class Transition(Callbacks):
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
        super().__init__(on_transfer=on_transfer, condition=condition)
        self._validate(old_state, new_state)
        self.machine = machine
        self.trigger = trigger
        self.old_path = Path(old_state)
        self.new_path = Path(new_state)
        self.old_state = self.old_path.get_in(machine)
        self.new_state = self.new_path.get_in(machine)
        self.exit_states = tuple(self.old_path.iter_out(self.machine))
        self.entry_states = tuple(self.new_path.iter_in(self.machine))
        self.new_state_name = str(self.machine.full_path + self.new_path)  # + self.new_path.get_in(self.machine).default_path
        self.info = info

    @lazy_property
    def obj_key(self):
        return self.machine.root.dict_key

    def execute(self, obj, *args, **kwargs):
        if self.do_condition(obj, *args, **kwargs):
            if self.old_state is self.new_state:
                self.old_state.do_on_stay(obj, *args, **kwargs)
                self.do_on_transfer(obj, *args, **kwargs)
            else:
                for state in self.exit_states:
                    state.do_on_exit(obj, *args, **kwargs)
                setattr(obj, self.obj_key, self.new_state_name)
                self.do_on_transfer(obj, *args, **kwargs)
                for state in self.entry_states:
                    state.do_on_entry(obj, *args, **kwargs)
            return True
        return False

    def __str__(self):
        """ string representing the transition """
        return f"<{str(self.old_path)}, {str(self.new_path)}, trigger={self.trigger}>"

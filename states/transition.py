from states.tools import MachineError
from states.tools import Path, callbackify


class Transition(object):
    """class for the internal representation of transitions in the state machine"""

    def __init__(self, machine, old_state, new_state, trigger,
                 before_transfer=(), after_transfer=(), condition=None, info=""):
        """ after_transfer is from switched transition on_transfer specific for the new state """
        self.machine = machine
        self.trigger = trigger
        self.old_path = Path(old_state)
        self.new_path = Path(new_state)
        self._validate(old_state, new_state)
        try:
            self.old_state = self.old_path.get_in(machine)
            self.new_state = self.new_path.get_in(machine)
        except KeyError as e:
            raise MachineError(f"non-existing state {e} when constructing transitions")
        self.same_state = self._old_is_new()
        self.before_transfer = callbackify(before_transfer)
        self.after_transfer = callbackify(after_transfer)
        self.condition = callbackify(condition)
        self.new_obj_path = self.machine.full_path + self.new_path + self.new_path.get_in(self.machine).default_path
        self.info = info

    def _old_is_new(self):
        return not hasattr(self.old_state, 'sub_states') and self.old_state is self.new_state

    def _validate(self, old_state, new_state):
        """ assures that no internal transitions are defined on an outer state level"""
        old_states = old_state.split(".", 1)
        new_states = new_state.split(".", 1)
        if (len(old_states) > 1 or len(new_states) > 1) and old_states[0] == new_states[0]:
            raise MachineError("inner transitions in a nested state machine cannot be defined at the outer level")

    def update_state(self, obj):
        setattr(obj, self.machine.root.dkey, str(self.new_obj_path))

    def _execute(self, obj, *args, **kwargs):
        self.machine.do_prepare(obj, *args, **kwargs)
        with self.machine.context_manager(obj, *args, **kwargs):
            if self.condition(obj, *args, **kwargs) and self.new_state.condition(obj, *args, **kwargs):
                if self.same_state:
                    self.before_transfer(obj, *args, **kwargs)
                    self.old_state.on_stay(obj, *args, **kwargs)
                    self.after_transfer(obj, *args, **kwargs)
                else:
                    self.machine.do_exit(obj, *args, **kwargs)
                    self.before_transfer(obj, *args, **kwargs)
                    self.update_state(obj)
                    self.after_transfer(obj, *args, **kwargs)
                    self.machine.do_enter(obj, *args, **kwargs)
                return True
            return False

    def execute(self, obj, *args, **kwargs):
        self.machine.do_prepare(obj, *args, **kwargs)
        with self.machine.context_manager(obj, *args, **kwargs) as context:
            self._execute(obj, *args, **kwargs)


    def __str__(self):
        """string representing the transition"""
        return "<%s, %s>" % (str(self.old_path), str(self.new_path))
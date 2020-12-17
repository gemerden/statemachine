__author__ = "lars van gemerden"

from collections import defaultdict
from functools import partial

from states.machine import StateMachine


class StatefulObject(object):
    """
    Base class for objects with a state machine managed state. State can change by calling triggers as defined in
    transitions of the state machine.
    """

    @classmethod
    def set_state_machines(cls):
        cls._state_machines = {}
        for name in dir(cls):
            cls_attr = getattr(cls, name)
            if isinstance(cls_attr, StateMachine):
                cls._state_machines[name] = cls_attr

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._state_machines = {}
        for name in dir(cls):
            cls_attr = getattr(cls, name)
            if isinstance(cls_attr, StateMachine):
                cls._state_machines[name] = cls_attr

        trigger_funcs = defaultdict(list)
        for name, machine in cls._state_machines.items():
            for trigger_name in machine.triggers:
                trigger_func = partial(machine.trigger, trigger_name=trigger_name)
                trigger_funcs[trigger_name].append(trigger_func)

        for trigger_name, funcs in trigger_funcs.items():
            def composite_func(*args, _funcs=funcs, **kwargs):
                obj = None
                for func in _funcs:
                    obj = func(*args, **kwargs)  # same 'obj' every time
                return obj
            setattr(cls, trigger_name, composite_func)

    def __init__(self, *args, **kwargs):
        """
        Constructor for this base class. Initial state(s) can be given with the name of the state machine(s). If not given,
        the initial state will be the top state in param 'states' of the state machine(s).
        """
        self._init_state(kwargs)
        super().__init__(*args, **kwargs)

    def _init_state(self, kwargs):
        for name, machine in self._state_machines.items():
            setattr(self, name, str(machine.get_initial_path(kwargs.pop(name, ""))))

    def trigger_initial(self, *args, **kwargs):
        """ see StatefulObject, but now for multiple state machines """
        for machine in self._state_machines.values():
            machine.do_enter(self, *args, **kwargs)

    def trigger(self, name, *args, **kwargs):
        obj = None
        for machine in self._state_machines.values():
            if name in machine.triggers:
                obj = machine.trigger(self, name, *args, **kwargs)
        if obj is None:
            raise ValueError(f"'{self.__class__.__name__}' has no trigger '{name}'")
        return obj


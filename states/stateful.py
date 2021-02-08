__author__ = "lars van gemerden"

from collections import defaultdict
from functools import partial

from states.machine import StateMachine


class StatefulObject(object):
    """
    Base class for objects with a state machine managed state. State can change by calling triggers as defined in
    transitions of the state machine.
    """

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._state_machines = {}
        for name in dir(cls):
            cls_attr = getattr(cls, name)
            if isinstance(cls_attr, StateMachine):
                cls._state_machines[name] = cls_attr

        trigger_functions = defaultdict(list)
        for machine in cls._state_machines.values():
            for trigger in machine.triggers:  # the names
                function = partial(machine.trigger,
                                   trigger=trigger)
                trigger_functions[trigger].append(function)

        for trigger, functions in trigger_functions.items():
            def composite_func(self, *args, _functions=functions, **kwargs):
                for function in _functions:
                    function(self, *args, **kwargs)  # same 'obj' every time
                return self

            setattr(cls, trigger, composite_func)

    def __init__(self, *args, **kwargs):
        """
        Constructor for this base class. Initial state(s) can be given with the name of the state machine(s). If not given,
        the initial state will be the top state in param 'states' of the state machine(s).
        """
        for name, machine in self._state_machines.items():
            machine.set_state(self, kwargs.pop(name, ""))
        super().__init__(*args, **kwargs)

    def trigger_initial(self, *args, **kwargs):
        """ optionally call the 'on_entry' callbacks of the nested initial states """
        for machine in self._state_machines.values():
            machine.initial_entry(self, *args, **kwargs)

    def trigger(self, name, *args, **kwargs):
        getattr(self, name)(*args, **kwargs)

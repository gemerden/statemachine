__author__ = "lars van gemerden"

from collections import defaultdict
from functools import partial

from states.machine import StateMachine


class StatefulObject(object):
    """
    Base class for objects with one or more state machine managed states. State can change by calling triggers as defined in
    transitions of the state machine.
    """

    def __init_subclass__(cls, **kwargs):
        """
        Does 2 things:
            - Creates a class attribute dict '_state_machines' to be able to iterate over the state machines,
            - Creates the trigger methods for the subclass, making sure that calling the trigger is propagated
                to all state machines.
        """
        super().__init_subclass__(**kwargs)
        cls._state_machines = {}
        for name in dir(cls):
            cls_attr = getattr(cls, name)
            if isinstance(cls_attr, StateMachine):
                cls._state_machines[name] = cls_attr

        trigger_functions = defaultdict(list)
        for machine in cls._state_machines.values():
            for trigger in machine.triggers:  # the names
                function = partial(machine.trigger, trigger)
                trigger_functions[trigger].append(function)

        for trigger, functions in trigger_functions.items():

            def composite_trigger_function(self, *args, __trigger_functions=functions, **kwargs):
                for function in __trigger_functions:
                    function(self, *args, **kwargs)
                return self

            setattr(cls, trigger, composite_trigger_function)

    def __init__(self, *args, **kwargs):
        """
        Constructor for this base class. Initial state(s) can be given with the name of the state machine(s), as in:

            class Project(StatefulObject):
                on_time = state_machine("true", "false")

            project = Project(on_time="false")

         If not given, the initial state will be the first state in param 'states' of the state machine(s).
        """
        for name, machine in type(self)._state_machines.items():
            machine.set_state(self, kwargs.pop(name, ""))
        super().__init__(*args, **kwargs)

    def trigger_initial(self, *args, **kwargs):
        """
        Optionally use this to call the 'on_entry' callbacks of the initial state(s). Often after
        sub-class construction is completed
        """
        for machine in self._state_machines.values():
            machine.initial_entry(self, *args, **kwargs)


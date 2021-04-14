__author__ = "lars van gemerden"

from states.machine import StateMachine
from states.tools import class_attributes


class StatefulObject(object):
    """
    Base class for objects with one or more state machine managed states. State can change by calling triggers as defined in
    transitions of the state machine.
    """
    def __init_subclass__(cls, **kwargs):
        """ moved from StateMachine.__set_class__ for better error handling (no RunTimeError) and late binding """
        super().__init_subclass__(**kwargs)
        machine_dict = class_attributes(cls, filter=lambda a: isinstance(a, StateMachine))
        cls._state_machines = list(machine_dict.values())
        for name, machine in machine_dict.items():
            machine.bind(cls, name)
            machine.resolve_callbacks(cls)
            machine.validate_transitions()
            machine.install_triggers(cls)

    def __init__(self, *args, **kwargs):
        """
        Constructor for this base class. Initial state(s) can be given with the name of the state machine(s), as in:

            class Person(StatefulObject):
                mood = state_machine("good", "bad")

            project = Project(mood="good")

         If not given, the initial state will be the first state in param 'states' of the state machine(s).
        """
        for machine in self._state_machines:
            machine.set_from_kwargs(self, kwargs)
        super().__init__(*args, **kwargs)

    def trigger_initial(self, *args, **kwargs):
        """
        Optionally use this to call the 'on_entry' callbacks of the initial state(s). Often after
        sub-class construction is completed (and e.g. attributes are initialized).
        """
        for machine in self._state_machines:
            machine.init_entry(self, *args, **kwargs)


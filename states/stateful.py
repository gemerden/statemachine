__author__ = "lars van gemerden"


class StatefulObject(object):
    """
    Base class for objects with one or more state machine managed states. State can change by calling triggers as defined in
    transitions of the state machine.
    """

    _state_machines = None  # initialized by state machines on subclasses

    def __init_subclass__(cls, **kwargs):
        """ moved from StateMachine.__set_class__ for better error handling (no RunTimeError)"""
        super().__init_subclass__(**kwargs)
        for machine in cls._state_machines.values():
            machine.resolve_callbacks(cls)
            machine.install_triggers(cls)
            machine.validate()

    def __init__(self, *args, **kwargs):
        """
        Constructor for this base class. Initial state(s) can be given with the name of the state machine(s), as in:

            class Person(StatefulObject):
                mood = state_machine("good", "bad")

            project = Project(mood="good")

         If not given, the initial state will be the first state in param 'states' of the state machine(s).
        """
        for name, machine in self._state_machines.items():
            machine.set_state(self, kwargs.pop(name, ""))
        super().__init__(*args, **kwargs)

    def trigger_initial(self, *args, **kwargs):
        """
        Optionally use this to call the 'on_entry' callbacks of the initial state(s). Often after
        sub-class construction is completed (and e.g. attributes are initialized).
        """
        for machine in self._state_machines.values():
            machine.init_entry(self, *args, **kwargs)


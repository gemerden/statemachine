class StatefulObject(object):
    """
    Base class for objects with a state machine managed state. State can change by calling triggers as defined in
    transitions of the state machine.
    """

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
        return obj


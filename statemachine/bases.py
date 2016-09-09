from functools import partial

from statemachine.machine import TransitionError, StateMachine, MachineError
from statemachine.tools import Path, has_doubles


class StateObject(object):
    """
    Base class for objects with a state machine managed state. State can change by calling triggers as defined in
    transitions of the state machine or by setting the 'state' property.

    Note that self.machine must return the state machine of the object. This can be achieved by either:

     - setting it at class level of the sub-class,
     - setting it in the constructor of the sub-class,
     - creating a property returning the state machine in the subclass.

     The last 2 allow for different machines to be used for objects of the same class.
    """

    def __init__(self, initial=None, *args, **kwargs):
        """
        Constructor for the base class
        :param initial: a ('.'separated) string indicating the initial (sub-)state of the object; if None, take
                the initial state as configured in the machine (if configured, else an exception is raised).
        """
        super(StateObject, self).__init__(*args, **kwargs)
        self._state = self.machine.get_initial_path(initial)

    def __getattr__(self, trigger):
        """
        Allows calling the triggers to cause a transition; the triggers return a bool indicating whether the
            transition took place.
        :param trigger: name of the trigger
        :return: partial function that allows the trigger to be called like object.some_trigger()
        """
        if trigger in self.machine.triggers:
            return partial(self.machine.do_trigger, obj=self, trigger=trigger)
        raise AttributeError("'%s' object has no attribute '%s'" % (type(self).__name__, trigger))

    @property
    def state_path(self):
        return self._state

    def get_state(self):
        """ returns the current state, as a '.' separated string """
        return str(self._state)

    def set_state(self, state):
        """ Causes the state machine to call all relevant callbacks and change the state of the object """
        self.machine.set_state(self, Path(state))

    state = property(get_state, set_state)  # turn state into a property


class MachineManager(object):

    machine_class = StateMachine

    def __init__(self, *configs):
        if has_doubles([c["name"] for c in configs]):
            raise MachineError("MachineManager cannot have multiple machines with the same name")
        self.machines = {c["name"]: self.machine_class(**c) for c in configs}
        self.triggers = set(sum((m.triggers for m in self.machines), []))

    def get_initial_paths(self, initials):
        return {k: m.get_initial_path(initials.get(k)) for k, m in self.machines.iteritems()}

    def __len__(self):
        return len(self.machines)

    def __iter__(self):
        return iter(self.machines)

    def __contains__(self, name):
        return name in self.machines

    def __getitem__(self, key):
        return self.machines[key]

    def do_trigger(self, obj, trigger, **kwargs):
        return any(m.do_trigger(obj, trigger, **kwargs) for m in self if trigger in m.triggers)


class MultiStateObject(object):
    """
    Base class for objects with multiple states. This can be useful when handling different aspects of the same
     object. [simple example]

    Note that self.machines must return a MachineManager (above) with the state machines of the object, with the
    keys being the names of the state machines. This can be achieved by either:

     - setting it at class level of the subclass,
     - setting it in the constructor of the subclass,
     - creating a property returning the state machine in the subclass.

     The last 2 allow for different machines to be used for objects of the same class.
    """

    def __init__(self, initials=None, *args, **kwargs):
        """
        Constructor for the base class
        :param initials: a dict of machine_name: ('.'separated) string indicating the initial state of the object in
                that machine;
        """
        super(MultiStateObject, self).__init__(*args, **kwargs)
        self._states = self.machines.get_initial_paths(initials or {})

    def __getattr__(self, trigger):
        """
        Allows calling the triggers to cause a transition; the triggers return a bool indicating whether the
            transition took place.
        :param trigger: name of the trigger
        :return: partial function that allows the trigger to be called like object.some_trigger()
        """
        if trigger in self.machines.triggers:
            return partial(self.machines.do_trigger, obj=self, trigger=trigger)
        raise AttributeError("'%s' object has no attribute '%s'" % (type(self).__name__, trigger))

    def state_path(self, machine_name):
        return self._states[machine_name]

    def state(self, path_string=None):
        """  """
        if path_string:
            if '.' in path_string:
                name, state = '.'.split(path_string, 1)
                self.machines[name].set_state(self, Path(state))
            else:
                return str(self._states[path_string])
        else:
            return {m: str(s) for m, s in self._states.iteritems()}


if __name__ == "__main__":
    """
    Small usage example: a minimal state machine (see also the tests)
    """


    def printer(action):
        def func(obj):
            print "'%s' for '%s' results in transition to %s" % (action, str(obj), obj.state)

        return func


    class LightSwitch(StateObject):

        machine = StateMachine(
            name="matter machine",
            states=[
                {"name": "on", "on_exit": printer("turn off"), "on_entry": printer("turn on")},
                {"name": "off", "on_exit": printer("turn on"), "on_entry": printer("turn off")},
            ],
            transitions=[
                {"old_state": "off", "new_state": "on", "triggers": ["turn_on", "switch"]},
                {"old_state": "on", "new_state": "off", "triggers": ["turn_off", "switch"]},
            ],
        )

        def __init__(self, name, initial="off"):
            super(LightSwitch, self).__init__(initial=initial)
            self.name = name

        def __str__(self):
            return self.name + " (%s)" % self.state


    light_switch = LightSwitch("lights")

    print light_switch.turn_on()
    print light_switch, light_switch._state
    light_switch.turn_off()
    try:
        light_switch.turn_off()
    except TransitionError as e:
        print "error: " + e.message
    print
    light_switch.switch()
    light_switch.switch()
    print
    light_switch.state = "on"
    light_switch.state = "off"
    try:
        light_switch.state = "off"  # does not result in any callbacks because the switch is already off
    except TransitionError as e:
        print e.message


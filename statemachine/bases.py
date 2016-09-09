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


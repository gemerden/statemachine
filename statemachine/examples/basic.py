from statemachine.bases import StatefulObject
from statemachine.machine import StateMachine, TransitionError

__author__  = "lars van gemerden"


if __name__ == "__main__":
    """
    Small usage example: a minimal state machine (see also the tests)
    """


    def printer(action):
        def func(obj):
            print "'%s' for '%s' results in transition to %s" % (action, str(obj), obj.state)

        return func


    class LightSwitch(StatefulObject):

        machine = StateMachine(
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


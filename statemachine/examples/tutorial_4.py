from statemachine.baseclass import StatefulObject
from statemachine.machine import StateMachine

class LightSwitch(StatefulObject):

    machine = StateMachine(
        states=[
            {"name": "on", "on_entry": "time_printer"},
            {"name": "off", "on_entry": "time_printer"},
        ],
        transitions=[
            {"old_state": "off", "new_state": "on", "triggers": "flick", "on_transfer": "transfer_printer"},
            {"old_state": "on", "new_state": "off", "triggers": "flick", "on_transfer": "transfer_printer"},
        ],
    )

    def time_printer(self, time, **kwargs):
        print "switch turned %s at %s" % (self.state, str(time))

    def transfer_printer(self, name="who", **kwargs):
        print "%s is using the switch" % name

if __name__ == "__main__":

    from datetime import datetime

    lightswitch = LightSwitch(initial="off")
    lightswitch.flick(name="bob", time=datetime(1999, 12, 31, 23, 59))
    lightswitch.flick(time=datetime(2000, 1, 1, 0, 0))

    # prints:

    # bob is using the switch
    # switch turned on at 1999-12-31 23:59:00
    # who is using the switch
    # switch turned off at 2000-01-01 00:00:00

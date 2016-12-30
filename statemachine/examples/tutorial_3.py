from statemachine.machine import StateMachine, StatefulObject


def entry_printer(obj):
    print "%s entering state '%s'" % (str(obj), obj.state)

class LightSwitch(StatefulObject):

    machine = StateMachine(
        states=[
            {"name": "on", "on_exit": "exit_printer", "on_entry": entry_printer},
            {"name": "off", "on_exit": "exit_printer", "on_entry": entry_printer},
        ],
        transitions=[
            {"old_state": "off", "new_state": "on", "triggers": "flick", "on_transfer": "going"},
            {"old_state": "on", "new_state": "off", "triggers": "flick"},
        ],
        after_any_entry="success"
    )

    def exit_printer(self):
        print "%s exiting state '%s'" % (str(self), self.state)

    def going(self):
        print str(self), "flicking"

    def success(self):
        print "it worked"

    def __str__(self):
        return "lightswitch"

if __name__ == "__main__":

    lightswitch = LightSwitch(initial="off")  # setting the initial state does not call any callback functions
    assert lightswitch.state == "off"         # the lightswitch is now in the "off" state

    lightswitch.flick()                       # another trigger to change state
    assert lightswitch.state == "on"

    lightswitch.flick()                       # flick() works both ways
    assert lightswitch.state == "off"

    #prints:

    # lightswitch exiting state 'off'
    # lightswitch flicking
    # lightswitch entering state 'on'
    # it worked
    # lightswitch exiting state 'on'
    # lightswitch entering state 'off'
    # it worked

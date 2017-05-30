from statemachine.machine import state_machine, StatefulObject


def entry_printer(obj):
    print "%s entering state '%s'" % (str(obj), obj.state)

class LightSwitch(StatefulObject):

    state_machine = state_machine(
        states=[
            {"name": "on", "on_exit": "exit_printer", "on_entry": entry_printer},
            {"name": "off", "on_exit": "exit_printer", "on_entry": entry_printer},
        ],
        initial = "off",
        transitions=[
            {"old_state": "off", "new_state": "on", "triggers": "flick", "on_transfer": "transfer"},
            {"old_state": "on", "new_state": "off", "triggers": "flick"},
        ],
        after_any_entry="success"
    )

    def exit_printer(self):
        print "%s exiting state '%s'" % (str(self), self.state)

    def transfer(self):
        print str(self), "flicking"

    def success(self):
        print "it worked"

    def __str__(self):
        return "lightswitch"

if __name__ == "__main__":

    lightswitch = LightSwitch()
    lightswitch.initial = "off"  # setting the initial state does not call any callback functions
    lightswitch.flick()          # another trigger to change state
    lightswitch.flick()          # flick() works both ways

    #prints:

    # lightswitch exiting state 'off'
    # lightswitch flicking
    # lightswitch entering state 'on'
    # it worked
    # lightswitch exiting state 'on'
    # lightswitch entering state 'off'
    # it worked

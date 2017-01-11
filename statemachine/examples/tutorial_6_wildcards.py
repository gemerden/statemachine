from statemachine.machine import StateMachine, StatefulObject


class LightSwitch(StatefulObject):

    machine = StateMachine(
        states=[
            {"name": "on", "on_entry": "printer"},
            {"name": "off", "on_entry": "printer"},
            {"name": "broken", "on_entry": "printer"}
        ],
        transitions=[
            {"old_state": "off", "new_state": "on", "triggers": "flick"},
            {"old_state": "on", "new_state": "off", "triggers": "flick"},
            {"old_state": "*", "new_state": "broken", "triggers": "smash"},
            # or: {"old_state": ["on", "off"], "new_state": "broken", "triggers": "smash"},
            {"old_state": "broken", "new_state": "off", "triggers": "fix"},
        ],
    )

    def printer(self):
        print "entering state '%s'" % self.state


if __name__ == "__main__":

    lightswitch = LightSwitch(initial="off")
    lightswitch.flick()
    lightswitch.smash()
    lightswitch.fix()

    # prints:

    # entering state 'on'
    # entering state 'broken'
    # entering state 'off'


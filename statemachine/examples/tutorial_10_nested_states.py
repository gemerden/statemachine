from statemachine.machine import StateMachine, StatefulObject


class LightSwitch(StatefulObject):

    machine = StateMachine(
        states=[
            {
                "name": "normal",
                "states": [
                    {"name": "off"},
                    {"name": "on"},
                ],
                "transitions": [
                    {"old_state": "off", "new_state": "on", "triggers": "flick"},
                    {"old_state": "on", "new_state": "off", "triggers": "flick"},
                ]
             },
            {"name": "broken"}
        ],
        transitions=[
            {"old_state": "normal", "new_state": "broken", "triggers": "smash"},
            {"old_state": "broken", "new_state": "normal", "triggers": "fix"},
        ],
    )

    def printer(self):
        print "entering state '%s'" % self.state


if __name__ == "__main__":

    lightswitch = LightSwitch()
    lightswitch.flick()
    lightswitch.smash()
    lightswitch.fix()
    lightswitch.flick()

    assert lightswitch.state == "normal.on"


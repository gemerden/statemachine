from statemachine.machine import StateMachine, StatefulObject

class LightSwitch(StatefulObject):
    machine = StateMachine(
        states=[
            {"name": "on"},
            {"name": "off"},
        ],
        transitions=[
            {"old_state": "off", "new_state": "on", "triggers": "flick", "condition": "is_nighttime"},  # switch only turns on at night
            {"old_state": "on", "new_state": "off", "triggers": "flick"},
        ],
    )

    def __init__(self, *args, **kwargs):
        super(LightSwitch, self).__init__(*args, **kwargs)
        self.daytime = False

    def is_nighttime(self):
        return not self.daytime


if __name__ == "__main__":
    switch = LightSwitch(initial="off")
    assert switch.is_nighttime()
    switch.flick()
    assert switch.state == "on"
    switch.flick()
    assert switch.state == "off"
    switch.daytime = True
    switch.flick()
    assert switch.state == "off"
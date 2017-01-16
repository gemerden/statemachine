from statemachine.machine import StateMachine, StatefulObject

class LightSwitch(StatefulObject):
    machine = StateMachine(
        states=[
            {"name": "on"},
            {"name": "off"},
        ],
        transitions=[
            {"old_state": "off", "new_state": "on", "triggers": "flick", "condition": "is_night"},  # switch only turns on at night
            {"old_state": "on", "new_state": "off", "triggers": "flick"},
        ],
    )

    def __init__(self, time=0, *args, **kwargs):
        super(LightSwitch, self).__init__(*args, **kwargs)
        self.time = time

    def flick(self, hours):
        self.time = (self.time + hours)%24  # increment time with hours and start counting from 0 if >24 (midnight)
        self.machine.trigger(self, "flick")

    def is_night(self):
        return self.time < 6 or self.time > 18


if __name__ == "__main__":
    switch = LightSwitch(time=0, initial="on")
    assert switch.is_night()
    switch.flick(hours=7)  # switch.time == 7
    assert switch.state == "off"
    switch.flick(hours=7)  # switch.time == 14
    assert switch.state == "off"
    switch.flick(hours=7)  # switch.time == 21
    assert switch.state == "on"

from states.machine import state_machine, StatefulObject

class LightSwitch(StatefulObject):

    machine = state_machine(
        name="matter machine",
        states=[
            {"name": "on"},
            {"name": "off"},
            {"name": "broken"}
        ],
        transitions=[
            {"old_state": "off", "new_state": "on", "triggers": "flick"},
            {"old_state": "on", "new_state": "off", "triggers": "flick"},
            {"old_state": ["on", "off"], "new_state": "broken", "triggers": "smash"},
            {"old_state": "broken", "triggers": "fix", "new_states": [{"name": "on", "condition": "was_on"},
                                                                      {"name": "off"}]},
        ],
        before_any_exit="store_state"  # this callback method is used to store the old state before transitioning
    )

    def __init__(self, initial=None):
        super(LightSwitch, self).__init__(initial=initial)
        self.old_state = None

    def store_state(self):
        self.old_state = self.state

    def was_on(self):
        return self.old_state == "on"

if __name__ == "__main__":
    switch = LightSwitch(initial="off")
    switch.smash()
    switch.fix()
    assert switch.state == "off"

    switch = LightSwitch(initial="on")
    switch.smash()
    switch.fix()
    assert switch.state == "on"


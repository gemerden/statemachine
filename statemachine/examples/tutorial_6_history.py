from statemachine.machine import state_machine, StatefulObject

class LightSwitch(StatefulObject):

    state_machine = state_machine(
        states=[
            {"name": "on"},
            {"name": "off"},
        ],
        transitions=[
            {"old_state": "off", "new_state": "on", "triggers": "flick"},
            {"old_state": "on", "new_state": "off", "triggers": "flick"},
        ],
        after_any_entry="store_in_history"
    )

    def __init__(self):
        self.history = [self.state]  # store the initial state

    def store_in_history(self, **kwargs):
        self.history.append(self.state)

if __name__ == "__main__":

    lightswitch = LightSwitch()
    lightswitch.flick()
    lightswitch.flick()
    lightswitch.flick()
    assert lightswitch.history == ["on", "off", "on", "off"]

from contextlib import contextmanager
from statemachine.machine import state_machine, StatefulObject

class LightSwitch(StatefulObject):

    state_machine = state_machine(
        states=[
            {"name": "on"},
            {"name": "off"},
        ],
        transitions=[
            {"old_state": "off", "new_state": "on", "triggers": "flick", "on_transfer": "assert_managed"},
            {"old_state": "on", "new_state": "off", "triggers": "flick", "on_transfer": "assert_managed"},
        ],
        context_manager="do_context"
    )

    def __init__(self):
        self.managed = False

    @contextmanager
    def do_context(self, **kwargs):
        self.managed = True
        yield
        self.managed = False

    def assert_managed(self, **kwargs):  # checks if the `managed` attribute is set to True during transition
        assert self.managed


if __name__ == "__main__":

    lightswitch = LightSwitch()
    assert not lightswitch.managed
    lightswitch.flick()
    assert not lightswitch.managed

from contextlib import contextmanager

from statemachine.machine import state_machine, StatefulObject


class LightSwitch(StatefulObject):

    machine = state_machine(
        states=[
            {
                "name": "normal",
                "on_exit": "on_exit_from_normal",
                "states": [
                    {"name": "off", "on_exit": "on_exit_from_off"},
                    {"name": "on", "on_entry": "on_entry_of_on", "on_exit": "on_exit_from_on", "condition": "on_state_condition"},
                ],
                "transitions": [
                    {"old_state": "off", "new_state": "on", "triggers": "flick",
                        "on_transfer": "on_transfer_from_off_to_on", "condition": "off_on_transition_condition"},
                    {"old_state": "on", "new_state": "off", "triggers": "flick"},
                ],
                "prepare": "prepare_in_normal",
                "before_any_exit": "before_any_exit_in_normal",  #within this (sub-) state machine
                "context_manager": "normal_context_manager",

            },
            {
                "name": "broken",
                "on_entry": "on_entry_of_broken",
                "condition": "broken_state_condition",
            }
        ],
        transitions=[
            {"old_state": "normal", "new_state": "broken", "triggers": "smash",
                "on_transfer": "on_transfer_from_normal_to_broken", "condition": "normal_broken_transition_condition"},
            {"old_state": "broken", "new_state": "normal", "triggers": "fix"},
        ],
        prepare = "prepare",
        before_any_exit = "before_any_exit",
        after_any_entry = "after_any_entry",
        context_manager = "context_manager",
    )

    def prepare_in_normal(self, *args, **kwargs):
        print "prepare in 'normal', state =", self.state

    def prepare(self, *args, **kwargs):
        print "prepare in main state machine, state =", self.state

    def on_exit_from_normal(self, *args, **kwargs):
        print "on_exit of 'normal', state =", self.state

    def on_exit_from_off(self, *args, **kwargs):
        print "on_exit of 'normal.off', state =", self.state

    def on_exit_from_on(self, *args, **kwargs):
        print "on_exit of 'normal.on', state =", self.state

    def on_entry_of_on(self, *args, **kwargs):
        print "on_entry of 'normal.on', state =", self.state

    def on_entry_of_broken(self, *args, **kwargs):
        print "on_entry of 'broken', state =", self.state

    def before_any_exit_in_normal(self, *args, **kwargs):
        print "before_any_exit in 'normal', state = ", self.state

    def before_any_exit(self, *args, **kwargs):
        print "before_any_exit in main state machine, state = ", self.state

    def after_any_entry(self, *args, **kwargs):
        print "after_any_entry in main state machine, state = ", self.state

    def on_transfer_from_off_to_on(self, *args, **kwargs):
        print "on_transfer from 'normal.off' to 'normal.on', state =", self.state

    def on_transfer_from_normal_to_broken(self, *args, **kwargs):
        print "on_transfer from 'normal' to 'broken', state =", self.state

    def on_state_condition(self, *args, **kwargs):
        print "checking condition of 'normal.on' state, state =", self.state
        return True

    def broken_state_condition(self, *args, **kwargs):
        print "checking condition of 'broken' state while in", self.state
        return True

    def off_on_transition_condition(self, *args, **kwargs):
        print "checking condition of 'normal.off' to 'normal.on', state =", self.state
        return True

    def normal_broken_transition_condition(self, *args, **kwargs):
        print "checking condition of 'normal' to 'broken', state =", self.state
        return True

    @contextmanager
    def normal_context_manager(self, *args, **kwargs):
        print "entering context for 'normal', state =", self.state
        yield
        print "exiting context for 'normal', state =", self.state

    @contextmanager
    def context_manager(self, *args, **kwargs):
        print "entering main context, state =", self.state
        yield
        print "exiting main context, state =", self.state



if __name__ == "__main__":

    lightswitch = LightSwitch(initial="normal.off")
    lightswitch.flick()
    print "-"
    lightswitch.smash()

    assert lightswitch.state == "broken"


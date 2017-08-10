from states.machine import state_machine, TransitionError, StatefulObject


class LightSwitch(StatefulObject):
    machine = state_machine(
        states=[
            {"name": "on"},
            {"name": "off"},
        ],
        transitions=[
            {"old_state": "off", "new_state": "on", "triggers": ["turn_on", "flick"]},  # adds two triggers for this transition
            {"old_state": "on", "new_state": "off", "triggers": ["turn_off", "flick"]},
        ],
    )


if __name__ == "__main__":
    lightswitch = LightSwitch(initial="off")  # argument "initial" defines the initial state
    assert lightswitch.state == "off"  # the lightswitch is now in the "off" state

    lightswitch.turn_on()  # triggering "turn_on" turns the switch on
    assert lightswitch.state == "on"  # the switch is now "on"

    lightswitch.turn_off()  # turning the switch back off
    assert lightswitch.state == "off"  # the switch is now "off" again

    try:
        lightswitch.turn_off()  # cannot turn the switch off, it is already off (and there is no transition "off" to "off")
    except TransitionError:
        pass
    assert lightswitch.state == "off"  # the object is still in a legal state!

    lightswitch.flick()  # another trigger to change state
    assert lightswitch.state == "on"

    lightswitch.flick()  # flick() works both ways
    assert lightswitch.state == "off"

from statemachine.machine import state_machine, TransitionError, StatefulObject


class LightSwitch(StatefulObject):  # inherit from "StatefulObject" to get stateful behaviour

    machine = state_machine(
        states=[
            {"name": "on"},
            {"name": "off"},
        ],
        transitions=[
            {"old_state": "off", "new_state": "on"},
            {"old_state": "on", "new_state": "off"},
        ],
    )


if __name__ == "__main__":
    lightswitch = LightSwitch(initial="off")  # argument "initial" defines the initial state
    assert lightswitch.state == "off"  # the lightswitch is now in the "off" state

    lightswitch.state = "on"  # you can explicitly set the state through the "state" property
    assert lightswitch.state == "on"

    lightswitch.state = "on"  # this will not raise an exception, although there is no transition from "on" to "on"
    assert lightswitch.state == "on"

    try:
        lightswitch.state = "nix"  # this will not raise an exception; there is no state "nix"
    except TransitionError:
        pass
    assert lightswitch.state == "off"

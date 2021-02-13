import pstats, cProfile as profile

from states import StatefulObject, state_machine, state, transitions, transition, states


class Lamp(StatefulObject):
    state = state_machine(states(off=state(),
                                 on=state()),
                          transitions(transition("off", "on", trigger="flick"),
                                      transition("on", "off", trigger="flick")))


def run_transitions(count):
    lamp = Lamp()
    for _ in range(count):
        lamp.flick()
    return lamp


if __name__ == '__main__':
    profile.run('run_transitions(100_000)')

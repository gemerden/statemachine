import pstats, cProfile as profile
from pstats import SortKey

from states import StatefulObject, state_machine, state, transitions, transition, states


class Lamp(StatefulObject):
    state = state_machine(states(off=state(),
                                 on=state()),
                          transitions(transition("off", "on", trigger="flick"),
                                      transition("on", "off", trigger="flick")))

    def __init__(self):
        super().__init__()
        self.on_count = 0
        self.off_count = 0

    @state.on_entry('on')
    def inc_on_count(self, **kwargs):
        self.on_count += 1


    @state.on_entry('off')
    def inc_off_count(self, **kwargs):
        self.off_count += 1


def run_transitions(count):
    lamp = Lamp()
    for _ in range(count):
        lamp.flick()
    return lamp


if __name__ == '__main__':
    profile.run('run_transitions(100_000)', './data/profile')

    p = pstats.Stats('./data/profile')
    p.strip_dirs().sort_stats(SortKey.TIME).print_stats(20)
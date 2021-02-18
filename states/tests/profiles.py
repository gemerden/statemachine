import pstats, cProfile as profile

from states import StatefulObject, state_machine, state, transitions, transition, states
from states.tools import stopwatch


class Lamp(StatefulObject):
    state = state_machine(states=states(off=state(),
                                        on=state()),
                          transitions=(transition("off", "on", trigger="flick"),
                                       transition("on", "off", trigger="flick")))

    @state.on_entry('on')
    def inc_on_count(self):
        pass

    @state.on_entry('off')
    def inc_off_count(self):
        pass


def run_transitions(count):
    lamp = Lamp()
    with stopwatch() as stop_time:
        for _ in range(count):
            lamp.flick()
    return stop_time()

def r(v):
    return f'{v:.4E}'


if __name__ == '__main__':
    N = 100000

    profile.run(f"run_transitions({N})", './data/profile')

    p = pstats.Stats('./data/profile')
    p.strip_dirs().sort_stats(pstats.SortKey.TIME).print_stats(20)

    lamp = Lamp()
    time = 1
    times = []
    while time > 0.7e-6:
        with stopwatch() as stop_time:
            for _ in range(N):
                lamp.flick()
        time = stop_time()/N
        times.append(time)
        count = len(times)
        print(count, '- time per transition:', r(time),
              'min:', r(min(times)), 'max:', r(max(times)), 'average:', r(sum(times)/count), 'median:', r(times[count//2]))

import unittest
from itertools import product

from ..tools import Path
from ..configuration import transitions, default_case, states, state, transition, switch, case
from ..normalize import normalize_statemachine_config


def count(it, key):
    return len([i for i in it if key(i)])


class TestStatemachineStandardizarion(unittest.TestCase):

    def iter_configs(self, config, include_leaves=True):
        yield config
        if config.get('states'):
            for state_config in config['states'].values():
                if state_config.get('states') or include_leaves:
                    yield from self.iter_configs(state_config)

    def states(self, config):
        states = set()
        for config in self.iter_configs(config):
            states_dict = config.get('states', {})
            states.update(states_dict)
        return states

    def transitions(self, config):
        transitions = []
        for config in self.iter_configs(config):
            trans_list = config.get('transitions', [])
            transitions.extend(trans_list)
        return transitions

    def assert_transition(self, trans, config, states):
        old_state = trans['old_state']
        new_state = trans['new_state']
        assert isinstance(old_state, str)
        assert isinstance(new_state, str)
        assert '*' not in old_state
        assert '*' not in new_state
        for name in Path(old_state):
            assert name in states
        for name in Path(new_state):
            assert name in states

    def assert_standard_config(self, config):
        states = self.states(config)
        for state_config in self.iter_configs(config):
            for trans in state_config.get('transitions', ()):
                self.assert_transition(trans, state_config, states)

    """ actual tests """

    def test_simple(self):
        config = dict(states=states(off=state(info="not turned on"),
                                    on=state(info="not turned off")),
                      transitions=transitions(transition("off", "on", trigger="turn_on", info="turn the light on"),
                                              transition("on", "off", trigger="turn_off", info="turn the light off"),
                                              transition("off", "off", trigger="leave", info="do nothing")))

        standard_config = normalize_statemachine_config(**config)

        self.assert_standard_config(standard_config)

    def test_with_wildcards(self):
        config = dict(states=states(off=state(info="not turned on"),
                                    on=state(info="not turned off")),
                      transitions=transitions(transition("*", "on", trigger="turn_on", info="turn the light on"),
                                              transition("*", "off", trigger="turn_off", info="turn the light off")))

        standard_config = normalize_statemachine_config(**config)
        self.assert_standard_config(standard_config)

        standard_transitions = self.transitions(standard_config)
        assert len(standard_transitions) == 4
        assert set((t['old_state'], t['new_state']) for t in standard_transitions) == set(product(('on', 'off'),
                                                                                                  ('on', 'off')))

    def test_with_multiple_old_states(self):
        config = dict(states=states(off=state(info="not turned on"),
                                    on=state(info="not turned off")),
                      transitions=transitions(transition(('on', 'off'), "on", trigger="turn_on", info="turn the light on"),
                                              transition(('on', 'off'), "off", trigger="turn_off", info="turn the light off")))

        standard_config = normalize_statemachine_config(**config)
        self.assert_standard_config(standard_config)

        standard_transitions = self.transitions(standard_config)
        assert len(standard_transitions) == 4
        assert set((t['old_state'], t['new_state']) for t in standard_transitions) == set(product(('on', 'off'),
                                                                                                  ('on', 'off')))

    def test_with_callbacks(self):
        """ bit moot """
        config = dict(states=states(off=state(on_entry=lambda v: 0, info="not turned on"),
                                    on=state(info="not turned off")),
                      transitions=transitions(transition("off", "on", trigger="turn_on", info="turn the light on"),
                                              transition("on", "off", trigger="turn_off", info="turn the light off")))

        standard_config = normalize_statemachine_config(**config)
        self.assert_standard_config(standard_config)

        assert callable(standard_config['states']['off']['on_entry'])

    def test_with_switches(self):
        config = dict(
            states=states(on=state(),
                          off=state(),
                          broken=state()),
            transitions=transitions(transition('off', 'on', trigger="flip"),
                                    transition('on', 'off', trigger="flip"),
                                    transition(["on", "off"], 'broken', trigger="smash"),
                                    transition('broken', switch(case('on', 'condition_func'),
                                                                default_case('off')),
                                               trigger='fix')),
        )
        standard_config = normalize_statemachine_config(**config)
        self.assert_standard_config(standard_config)

        standard_transitions = self.transitions(standard_config)
        assert len(standard_transitions) == 6
        assert count(standard_transitions, key=lambda t: t['condition']) == 1

    def test_with_nested_states(self):
        config = dict(
            states=states(off=state(states(working=state(),
                                           broken=state()),
                                    transitions(transition('broken', 'working', trigger='fix'))),
                          on=state(states(waiting=state(),
                                          washing=state(),
                                          drying=state()),
                                   transitions(transition('waiting', 'washing', trigger='wash'),
                                               transition('drying', 'waiting', trigger='stop')))),
            transitions=transitions(transition('off.working', 'on', trigger="turn_on"),
                                    transition('on.washing', 'on.drying', trigger='dry'),  # to test push-down -> 'on'
                                    transition('on', 'off', trigger="turn_off"),
                                    transition(('on.*', 'off'), 'off.broken', trigger=["smash"]),
                                    transition('off.working', 'on.drying', trigger=["just_dry_already"]))
        )

        standard_config = normalize_statemachine_config(**config)
        self.assert_standard_config(standard_config)

        standard_transitions = self.transitions(standard_config)
        assert len(standard_transitions) == 14

        assert list(standard_config['states'].keys()) == ['off', 'on']
        assert list(standard_config['states']['off']['states'].keys()) == ['working', 'broken']
        assert list(standard_config['states']['on']['states'].keys()) == ['waiting', 'washing', 'drying']

    def test_multiple_old_states_with_conditions(self):
        config = dict(
            states=states(on=state(),
                          off=state(),
                          broken=state()),
            transitions=transitions(transition('off', 'on', trigger="flip"),
                                    transition('on', 'off', trigger="flip"),
                                    transition(["on", "off"], 'broken', trigger="smash"),
                                    transition(('broken', 'off'), switch(case('on', 'condition_func'),
                                                                         default_case('off')),
                                               trigger='fix')),
        )
        standard_config = normalize_statemachine_config(**config)
        self.assert_standard_config(standard_config)

        standard_transitions = self.transitions(standard_config)
        assert len(standard_transitions) == 8
        assert count(standard_transitions, key=lambda t: t['condition']) == 2

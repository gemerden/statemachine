__author__ = "lars van gemerden"

import random
import unittest
from contextlib import contextmanager
from copy import deepcopy

from states import StatefulObject, TransitionError, MachineError, states, state, transition, state_machine

from ..tools import Path


def count_transitions(state):
    return len(list(state.iter_transitions()))


class TestSimplestStateMachine(unittest.TestCase):

    def setUp(self):
        self.config = dict(
            states={
                "off": {"info": "not turned on"},
                "on": {"info": "not turned off"},
            },
            transitions=[
                {"old_state": "off", "new_state": "on", "trigger": "switch", "info": "turn the light on"},
                {"old_state": "on", "new_state": "off", "trigger": "switch", "info": "turn the light off"},
            ],
        )
        self.config_copy = deepcopy(self.config)

        class LightSwitch(StatefulObject):
            state = state_machine(**self.config)

        self.light = LightSwitch()

    def test_construction(self):
        """test whether all states, transitions and trigger(s) are in place"""
        self.assertEqual(len(type(self.light).state), 2)
        self.assertEqual(count_transitions(type(self.light).state), 2)

    def test_triggers(self):
        """test the basio trigger functions and the resultig states"""
        self.assertEqual(self.light.state, "off")
        self.light.switch()
        self.assertEqual(self.light.state, "on")
        self.light.switch()
        self.assertEqual(self.light.state, "off")

    def test_info(self):
        self.assertEqual(type(self.light).state.sub_states["on"].info, "not turned off")
        self.assertEqual(type(self.light).state['off'].transitions['switch'][Path('on')].info, "turn the light on")


class TestStateMachine(unittest.TestCase):

    def setUp(self):
        """called before any individual test method"""
        self.callback_counter = 0  # rest for every tests; used to count number of callbacks from machine
        self.temperature_ignore = True  # used to switch condition function on or off

        def callback(obj, **kwargs):
            """checks whether the object arrives; callback_counter is used to check whether callbacks are all called"""
            self.assertEqual(type(obj), Matter)
            self.callback_counter += 1

        def temp_checker(min, max):
            """some configurable condition function; only in effect when temperature_ignore==False (some tests)"""

            def inner(obj, **kwargs):
                return min < obj.temperature <= max or self.temperature_ignore

            return inner

        self.config = dict(
            states={
                "solid": {"on_entry": [callback], "on_exit": [callback], "on_stay": ['do_on_stay']},
                "liquid": {"on_entry": [callback], "on_exit": [callback]},
                "gas": {"on_entry": [callback], "on_exit": [callback]}
            },
            transitions=[
                {"old_state": "solid", "new_state": "liquid", "trigger": ["melt", "heat"], "on_transfer": [callback],
                 "condition": temp_checker(0, 100)},
                {"old_state": "liquid", "new_state": "gas", "trigger": ["evaporate", "heat"], "on_transfer": callback,
                 "condition": temp_checker(100, float("inf"))},
                {"old_state": "gas", "new_state": "liquid", "trigger": ["condense", "cool"], "on_transfer": ["do_callback"],
                 "condition": temp_checker(0, 100)},
                {"old_state": "liquid", "new_state": "solid", "trigger": ["freeze", "cool"], "on_transfer": "do_callback",
                 "condition": temp_checker(-274, 0)}
            ],
        )

        class Matter(StatefulObject):
            """object class fo which the state is managed"""
            state = state_machine(**self.config)

            def __init__(self, name, temperature=0, state="solid"):
                super(Matter, self).__init__(state=state)
                self.name = name
                self.temperature = temperature  # used in tests of condition callback in transition class
                self.stayed = 0

            def do_callback(self, **kwargs):
                """used to test callback lookup by name"""
                callback(self, **kwargs)

            def heat_by(self, delta):
                """used to check condition on transition"""
                assert delta >= 0
                self.temperature += delta
                return self.heat()

            def cool_by(self, delta):
                """used to check condition on transition"""
                assert delta >= 0
                self.temperature -= delta
                return self.cool()

            def do_on_stay(self, **kwargs):
                self.stayed += 1

            def __str__(self):
                return self.name + "(%s)" % self.state

        self.object_class = Matter
        self.block = Matter("block")
        self.machine = Matter.state

    def test_construction(self):
        """test whether all states, transitions and trigger(s) are in place"""
        self.assertEqual(len(self.machine), 3)
        self.assertEqual(count_transitions(self.machine), 16)

    def test_state_names(self):
        self.assertEqual(list(self.machine), ['solid', 'liquid', 'gas'])

    def test_triggers_property(self):
        self.assertEqual(self.machine.triggers, {'heat', 'melt', 'cool', 'evaporate', 'freeze', 'condense'})

    def test_initial(self):
        class Dummy(StatefulObject):
            state = state_machine(**self.config)

            def do_callback(self, **kwargs):
                pass

            def do_on_stay(self, **kwargs):
                pass

        dummy = Dummy(state='gas')
        assert dummy.state == "gas"

    def test_triggers(self):
        """test the basio trigger functions and the resultig states"""
        self.block.melt()
        self.assertEqual(self.block.state, "liquid")
        self.block.evaporate()
        self.assertEqual(self.block.state, "gas")
        self.block.condense()
        self.assertEqual(self.block.state, "liquid")
        self.block.freeze()
        self.assertEqual(self.block.state, "solid")

    def test_shared_triggers(self):
        """test the shared trigger functions (same name for multiple transitions) and the resulting states"""
        self.block.heat()
        self.assertEqual(self.block.state, "liquid")
        self.block.heat()
        self.assertEqual(self.block.state, "gas")
        self.block.cool()
        self.assertEqual(self.block.state, "liquid")
        self.block.cool()
        self.assertEqual(self.block.state, "solid")

    def test_callback(self):
        """tests whether all callbacks are called during transitions"""
        self.block.melt()
        self.assertEqual(self.callback_counter, 3)
        self.block.heat()
        self.assertEqual(self.callback_counter, 6)
        self.block.cool()
        self.assertEqual(self.callback_counter, 9)
        self.block.cool()
        self.assertEqual(self.callback_counter, 12)

    def test_condition(self):
        """tests whether the condition callback works: if the condition fails, no transition takes place"""
        self.temperature_ignore = False
        block = self.object_class("block", temperature=-10)

        block = block.heat_by(5)
        assert block.temperature == -5
        self.assertEqual(self.block.state, "solid")
        self.assertEqual(self.callback_counter, 0)

        block = block.heat_by(10)
        assert block.temperature == 5
        self.assertEqual(block.state, "liquid")
        self.assertEqual(self.callback_counter, 3)

        block = block.heat_by(10)
        self.assertEqual(block.state, "liquid")
        self.assertEqual(self.callback_counter, 3)

        block = block.heat_by(100)
        self.assertEqual(block.state, "gas")
        self.assertEqual(self.callback_counter, 6)

    def test_on_stay(self):
        self.temperature_ignore = False
        block = self.object_class("block", temperature=-10)
        self.assertEqual(block.state, "solid")
        block.heat(delta=1)
        self.assertEqual(block.state, "solid")
        self.assertEqual(block.stayed, 1)

    def test_transition_errors(self):
        """tests whether non-existent transitions are detected"""
        block = self.object_class("block")
        with self.assertRaises(TransitionError):
            block.evaporate()
        with self.assertRaises(TransitionError):
            block.cool()
        self.assertEqual(block.state, "solid")

    def test_init_error(self):
        """tests whether a non-existing initial state is detected"""
        with self.assertRaises(TransitionError):
            self.object_class("block", state="plasma")

    def test_machine_errors(self):
        """tests whether double state names, transitions and trigger(s) and non-existing state names are detected"""
        with self.assertRaises(MachineError):
            state_machine(
                states={
                    "solid": {},
                    "liquid": {},
                },
                transitions=[
                    {"old_state": "solid", "new_state": "gas", "trigger": ["melt"]}
                ]
            )
        with self.assertRaises(MachineError):
            state_machine(
                states={
                    "solid": {},
                    "liquid": {},
                },
                transitions=[
                    {"old_state": "solid", "new_state": "liquid", "trigger": ["melt"]},
                    {"old_state": "solid", "new_state": "liquid", "trigger": ["melt"]},
                ]
            )
        with self.assertRaises(MachineError):
            state_machine(
                states={
                    "solid": {},
                    "liquid": {},
                    "gas": {},
                },
                transitions=[
                    {"old_state": "solid", "new_state": "liquid", "trigger": ["melt"]},
                    {"old_state": "liquid", "new_state": "gas", "trigger": ["evaporate"]},
                    {"old_state": "liquid", "new_state": "solid", "trigger": ["evaporate"]},
                ]
            )
        with self.assertRaises(TransitionError):
            class A(StatefulObject):
                state = state_machine(
                    states={
                        "solid": {},
                        "liquid": {},
                    },
                    transitions=[
                        {"old_state": "solid", "new_state": "liquid", "trigger": "trgr"},
                    ]
                )

            a = A()
            a.state = 'solid'


class TestWildcardStateMachine(unittest.TestCase):
    """test the case where transition configuration contains wildcards '*' """

    def setUp(self):
        """called before any individual test method"""
        self.callback_counter = 0  # rest for every tests; used to count number of callbacks from machine

        def callback(obj, **kwargs):
            """checks whether the object arrives; calback_counter is used to check whether callbacks are all called"""
            self.assertEqual(type(obj), Matter)
            self.callback_counter += 1

        # create a machine based on phase changes of matter (solid, liquid, gas)
        self.machine = state_machine(
            states={
                "solid": {"on_entry": [callback], "on_exit": [callback]},
                "liquid": {"on_entry": [callback], "on_exit": [callback]},
                "gas": {"on_entry": [callback], "on_exit": [callback]},
                "void": {"on_entry": [callback], "on_exit": [callback]}
            },
            transitions=[
                {"old_state": "solid", "new_state": "liquid", "trigger": ["melt", "heat"], "on_transfer": [callback]},
                {"old_state": "liquid", "new_state": "gas", "trigger": ["evaporate", "heat"], "on_transfer": [callback]},
                {"old_state": "gas", "new_state": "liquid", "trigger": ["condense", "cool"], "on_transfer": [callback]},
                {"old_state": "liquid", "new_state": "solid", "trigger": ["freeze", "cool"], "on_transfer": [callback]},
                {"old_state": "*", "new_state": "void", "trigger": ["zap"], "on_transfer": [callback]},
                {"old_state": "void", "new_state": "solid", "trigger": ["unzap"], "on_transfer": [callback]},
            ],
        )

        class Matter(StatefulObject):
            """object class fo which the state is managed"""
            state = self.machine

            def __init__(self, name, state="solid"):
                super(Matter, self).__init__(state=state)
                self.name = name

            def __str__(self):
                return self.name + "(%s)" % self.state

        self.object_class = Matter

    def test_construction(self):
        """test whether all states, transitions and trigger(s) are in place"""
        self.assertEqual(len(self.machine), 4)
        self.assertEqual(count_transitions(self.machine), 2 + 2 + 2 + 2 + 4 + 1)

    def test_triggers(self):
        """test the basio trigger functions and the resultig states"""
        block = self.object_class("block")
        block.zap()
        self.assertEqual(block.state, "void")
        block.unzap()
        self.assertEqual(block.state, "solid")
        block.zap()
        self.assertEqual(block.state, "void")

    def test_shared_triggers(self):
        """test the shared trigger functions (same name for multiple transitions) and the resulting states"""
        block = self.object_class("block")
        block.heat()
        self.assertEqual(block.state, "liquid")
        block.heat()
        self.assertEqual(block.state, "gas")

    def test_callback(self):
        """tests whether all callbacks are called during transitions"""
        block = self.object_class("block")
        block.melt()
        self.assertEqual(self.callback_counter, 3)
        block.heat()
        self.assertEqual(self.callback_counter, 6)
        block.cool()
        self.assertEqual(self.callback_counter, 9)
        block.zap()
        self.assertEqual(self.callback_counter, 12)
        block.zap()
        self.assertEqual(self.callback_counter, 13)

    def test_transition_exceptions(self):
        """tests whether non-existent transitions are detected"""
        block = self.object_class("block")
        self.assertEqual(block.state, 'solid')
        with self.assertRaises(TransitionError):
            block.evaporate()
        with self.assertRaises(TransitionError):
            block.cool()
        with self.assertRaises(TransitionError):
            block.cool()

    def test_machine_errors(self):
        """tests that new_state wildcard transitions cannot have trigger(s)"""
        with self.assertRaises(MachineError):
            state_machine(
                states={
                    "solid": {},
                    "liquid": {},
                    "gas": {},
                },
                transitions=[
                    {"old_state": "solid", "new_state": "*", "trigger": ["melt"]}
                ]
            )

    def test_double_wildcard(self):
        with self.assertRaises(MachineError):
            machine = state_machine(
                states={
                    "solid": {},
                    "liquid": {},
                },
                transitions=[
                    {"old_state": "*", "new_state": "*", "trigger": "do_it"},  # all transitions
                ],
            )


class TestListedTransitionStateMachine(unittest.TestCase):

    def setUp(self):
        self.callback_counter = 0  # rest for every tests; used to count number of callbacks from machine

        def callback(obj, **kwargs):
            """checks whether the object arrives; calback_counter is used to check whether callbacks are all called"""
            self.assertEqual(type(obj), Matter)
            self.callback_counter += 1

        # create a machine based on phase changes of matter (solid, liquid, gas)
        class Matter(StatefulObject):
            """object class fo which the state is managed"""
            state = state_machine(
                states={
                    "solid": {},
                    "liquid": {},
                    "gas": {},
                },
                transitions=[
                    {"old_state": ["solid", "liquid"], "new_state": "gas", "trigger": ["zap"]},
                    {"old_state": "gas", "new_state": "liquid", "trigger": ["cool"]},
                    {"old_state": "liquid", "new_state": "solid", "trigger": ["cool"]},
                ],
            )

            def __init__(self, name, state="solid"):
                super(Matter, self).__init__(state=state)
                self.name = name

            def __str__(self):
                return self.name + "(%s)" % self.state

        self.object_class = Matter
        self.machine = Matter.state

    def test_construction(self):
        """test whether all states, transitions and trigger(s) are in place"""
        self.assertEqual(len(self.machine.sub_states), 3)
        self.assertEqual(len(self.machine['solid'].transitions), 1)

    def test_transitions(self):
        """test whether transitions work in this case"""
        block = self.object_class("block")
        block.zap()
        self.assertEqual(block.state, "gas")
        block.cool()
        self.assertEqual(block.state, "liquid")
        block.cool()
        self.assertEqual(block.state, "solid")

    def test_error(self):
        """test transition error"""
        block = self.object_class("block", state="gas")
        with self.assertRaises(TransitionError):
            block.zap()


class TestSwitchedTransitionStateMachine(unittest.TestCase):

    def setUp(self):
        class LightSwitch(StatefulObject):
            state = state_machine(
                states={
                    "on": {},
                    "off": {},
                    "broken": {},
                },
                transitions=[
                    {"old_state": "off", "new_state": "on", "trigger": ["turn_on", "switch"]},
                    {"old_state": "on", "new_state": "off", "trigger": ["turn_off", "switch"]},
                    {"old_state": ["on", "off"], "new_state": "broken", "trigger": "smash"},
                    {"old_state": "broken", "trigger": "fix", "new_state": {"on": {"condition": "was_on"},
                                                                            "off": {}}},
                ],
            )

            def __init__(self, state=None):
                super(LightSwitch, self).__init__(state=state)
                self._old_state = None

            @state.on_exit('*')
            def store_state(self):
                self._old_state = self.state

            def was_on(self):
                return str(self._old_state) == "on"

        self.object_class = LightSwitch

    def test_off(self):
        light_switch = self.object_class(state="off")
        light_switch.smash()
        light_switch.fix()
        self.assertEqual(light_switch.state, "off")

    def test_on(self):
        light_switch = self.object_class(state="on")
        light_switch.smash()
        self.assertEqual(light_switch.state, "broken")
        light_switch.fix()
        self.assertEqual(light_switch.state, "on")

    def test_machine_error(self):
        with self.assertRaises(MachineError):
            state_machine(
                states={
                    "on": {},
                    "off": {},
                    "broken": {},
                },
                transitions=[
                    {"old_state": "off", "new_state": "on", "trigger": ["turn_on", "switch"]},
                    {"old_state": "on", "new_state": "off", "trigger": ["turn_off", "switch"]},
                    {"old_state": ["on", "off"], "new_state": "broken", "trigger": "smash"},
                    {"old_state": "broken", "new_state": "off", "trigger": "fix"},  # will first be checked
                    {"old_state": "broken", "new_state": "on", "trigger": "fix", "condition": "was_on"},
                ],
            )


class TestSwitchedDoubleTransitionStateMachine(unittest.TestCase):
    good_machine_dict = dict(
        states={
            "on": {},
            "off": {},
            "broken": {},
        },
        transitions=[
            {"old_state": "off", "new_state": "on", "trigger": ["turn_on", "switch"]},
            {"old_state": "on", "new_state": "off", "trigger": ["turn_off", "switch"]},
            {"old_state": ["on", "off"], "new_state": "broken", "trigger": "smash"},
            {"old_state": "broken", "trigger": "fix", "new_state": {"off": {"condition": lambda o: True},
                                                                    "broken": {}}},
            {"old_state": "broken", "new_state": "broken", "trigger": ["leave"]},
        ],
    )
    bad_machine_dict = dict(
        states={
            "on": {},
            "off": {},
            "broken": {},
        },
        transitions=[
            {"old_state": "off", "new_state": "on", "trigger": ["turn_on", "switch"]},
            {"old_state": "on", "new_state": "off", "trigger": ["turn_off", "switch"]},
            {"old_state": ["on", "off"], "new_state": "broken", "trigger": "smash"},
            {"old_state": "broken", "trigger": "FIX", "new_state": {"off": {"condition": lambda o: True},
                                                                    "broken": {}}},
            {"old_state": "broken", "new_state": "broken", "trigger": "FIX"},
        ],
    )

    machine_dict = dict(
        states={
            "on": {},
            "off": {},
            "broken": {},
        },
        transitions=[
            {"old_state": "off", "new_state": "on", "trigger": ["turn_on", "switch"]},
            {"old_state": "on", "new_state": "off", "trigger": ["turn_off", "switch"]},
            {"old_state": ["on", "off"], "new_state": "broken", "trigger": "smash"},
            {"old_state": "broken", "trigger": "fix", "new_state": {"off": {"condition": lambda o: True,
                                                                            "on_transfer": "do_after_transfer"},
                                                                    "broken": {}},
             "on_transfer": "do_before_transfer"},
            {"old_state": "broken", "new_state": "broken", "trigger": "leave"},
        ],
    )

    def test_good_double_transition(self):
        class Lamp(StatefulObject):
            state = state_machine(**deepcopy(self.good_machine_dict))

        self.assertEqual(count_transitions(Lamp.state), 9)

    def test_bad_double_transition(self):
        with self.assertRaises(MachineError):
            class Lamp(StatefulObject):
                state = state_machine(**deepcopy(self.bad_machine_dict))

    def test_transitions(self):
        class Lamp(StatefulObject):
            state = state_machine(**deepcopy(self.good_machine_dict))

        lamp = Lamp()
        self.assertEqual(lamp.state, "on")
        lamp.switch()
        self.assertEqual(lamp.state, "off")
        lamp.smash()
        self.assertEqual(lamp.state, "broken")
        lamp.fix()
        self.assertEqual(lamp.state, "off")
        lamp.smash()
        self.assertEqual(lamp.state, "broken")
        lamp.leave()
        self.assertEqual(lamp.state, "broken")

    def test_double_on_transfer(self):
        class Lamp(StatefulObject):
            state = state_machine(**deepcopy(self.machine_dict))

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.after_transfer = False

            def do_before_transfer(self):
                self.before_transfer = True

            def do_after_transfer(self):
                self.after_transfer = True

        lamp = Lamp(state='broken')
        self.assertEqual(lamp.state, "broken")
        lamp.fix()
        self.assertTrue(lamp.after_transfer)


class TestNestedStateMachine(unittest.TestCase):
    """test the case where transition configuration contains wildcards '*' """

    def setUp(self):
        """called before any individual test method"""
        self.exit_counter = 0  # reset for every tests; used to count number of callbacks from machine
        self.entry_counter = 0  # reset for every tests; used to count number of callbacks from machine
        self.before_counter = 0  # reset for every tests; used to count number of callbacks from machine

        def on_exit(obj, **kwargs):
            """basic check + counts the number of times the object exits a state"""
            self.assertEqual(type(obj), WashingMachine)
            self.exit_counter += 1

        def on_entry(obj, **kwargs):
            """basic check + counts the number of times the object enters a state"""
            self.assertEqual(type(obj), WashingMachine)
            self.entry_counter += 1

        # create a machine config based on phase changes of matter (solid, liquid, gas)
        self.machine_config = dict(
            states=dict(
                off=dict(
                    on_entry=on_entry,
                    on_exit=on_exit,
                    states={
                        "working": {"on_entry": on_entry, "on_exit": on_exit},
                        "broken": {"on_entry": on_entry, "on_exit": on_exit},
                    },
                    transitions=[
                        {"old_state": "working", "new_state": "broken", "trigger": ["smash"]},
                        {"old_state": "broken", "new_state": "working", "trigger": ["fix"]},
                    ],
                ),
                on=dict(
                    on_entry=on_entry,
                    on_exit=on_exit,
                    states={
                        "none": {"on_entry": on_entry, "on_exit": on_exit},
                        "washing": {"on_entry": on_entry, "on_exit": on_exit},
                        "drying": {"on_entry": on_entry, "on_exit": on_exit},
                    },
                    transitions=[
                        {"old_state": "none", "new_state": "washing", "trigger": ["wash"]},
                        {"old_state": "washing", "new_state": "drying", "trigger": ["dry"]},
                        {"old_state": "drying", "new_state": "none", "trigger": ["stop"]},
                    ]
                )
            ),
            transitions=[
                {"old_state": "off.working", "new_state": "on", "trigger": ["turn_on", "switch"]},
                {"old_state": "on", "new_state": "off", "trigger": ["turn_off", "switch"]},
                {"old_state": "on", "new_state": "off.broken", "trigger": ["smash"]},
                {"old_state": "off.working", "new_state": "on.drying", "trigger": ["just_dry_already"]},
            ],
        )

        class WashingMachine(StatefulObject):
            state = state_machine(**self.machine_config)

            @state.on_exit('*', 'off.*')
            def on_any_exit(obj, **kwargs):
                """ will be used to check whether this method will be looked up in super states """
                self.assertEqual(type(obj), WashingMachine)
                self.before_counter += 1

        self.object_class = WashingMachine

    def assert_counters(self, exit_counter, entry_counter, before_counter):
        self.assertEqual(self.exit_counter, exit_counter)
        self.assertEqual(self.entry_counter, entry_counter)
        self.assertEqual(self.before_counter, before_counter)

    def test_construction(self):
        """test whether all states, transitions and trigger(s) are in place"""
        self.assertEqual(len(self.object_class.state), 2)
        self.assertEqual(count_transitions(self.object_class.state), 17)
        child_state = self.object_class.state["on"]
        self.assertEqual(len(child_state), 3)
        self.assertEqual(count_transitions(child_state), 12)
        child_state = self.object_class.state["off"]
        self.assertEqual(count_transitions(child_state), 5)
        self.assertEqual(len(child_state['working'].transitions), 4)

    def test_len_in_getitem_iter_for_states(self):
        machine = self.object_class.state
        self.assertEqual(len(machine), 2)
        self.assertTrue("off" in machine)
        self.assertEqual(machine["on"].name, "on")
        self.assertEqual(machine["on"]["drying"].name, "drying")
        child_state = self.object_class.state["on"]
        self.assertEqual(len(child_state), 3)
        self.assertTrue("washing" in child_state)
        self.assertEqual(child_state["none"].name, "none")
        self.assertEqual(len([s for s in self.object_class.state]), 2)

    def test_getitem_for_transitions(self):
        machine = self.object_class.state
        self.assertEqual(machine["off.working", "turn_on"][Path("on.none")].state, machine["off"]["working"])
        self.assertEqual(machine["off.working", "turn_on"][Path("on.none")].target, machine["on"]["none"])
        self.assertEqual(str(machine["on"]["washing", "dry"][Path('on.drying')].state.path), "on.washing")
        self.assertEqual(str(machine["on"]["washing", "dry"][Path('on.drying')].target.path), "on.drying")
        self.assertEqual(str(machine["off.working", "just_dry_already", "on.drying"].state.path), "off.working")
        self.assertEqual(str(machine["off.working", "just_dry_already", "on.drying"].target.path), "on.drying")

    def test_in_for_transitions(self):
        machine = self.object_class.state
        self.assertTrue(("off.working", "on.drying") in machine)
        self.assertTrue(("washing", "drying") in machine["on"])
        self.assertTrue(("none", "washing") in machine["on"])

    def test_triggering(self):
        washer = self.object_class()
        self.assertEqual(washer.state, "off.working")
        self.assert_counters(0, 0, 0)

        washer.switch()
        self.assertEqual(washer.state, "on.none")
        self.assert_counters(2, 2, 2)

        washer.wash()
        self.assertEqual(washer.state, "on.washing")
        self.assert_counters(3, 3, 2)

        washer.dry()
        self.assertEqual(washer.state, "on.drying")
        self.assert_counters(4, 4, 2)

        washer.switch()
        self.assertEqual(washer.state, "off.working")
        self.assert_counters(6, 6, 3)

        washer.just_dry_already()
        self.assertEqual(washer.state, "on.drying")
        self.assert_counters(8, 8, 5)

    def test_state_string(self):
        self.assertEqual(str(self.object_class.state["on"]), "State('on')")
        self.assertEqual(str(self.object_class.state["on"]["washing"]), "State('on.washing')")

    def test_transition_errors(self):
        washer = self.object_class()
        self.assert_counters(0, 0, 0)
        self.assertEqual(washer.state, "off.working")

        with self.assertRaises(TransitionError):
            washer.dry()
        self.assertEqual(washer.state, "off.working")
        self.assert_counters(0, 0, 0)

        with self.assertRaises(TransitionError):
            washer.fix()
        self.assertEqual(washer.state, "off.working")
        self.assert_counters(0, 0, 0)

        washer.smash()
        self.assertEqual(washer.state, "off.broken")
        self.assert_counters(1, 1, 1)

        self.assertEqual(washer.state, "off.broken")
        self.assert_counters(1, 1, 1)

    def test_machine_errors(self):  # TODO
        assert "dry" in self.object_class.__dict__


class TestSwitchedTransition(unittest.TestCase):
    """test the case where transition configuration contains wildcards '*' """

    def setUp(self):
        # create a machine config based on phase changes of matter (solid, liquid, gas)
        self.machine_config = dict(
            states=dict(
                off={},
                on=dict(
                    states={
                        "none": {},
                        "washing": {},
                        "drying": {},
                    },
                    transitions=[
                        {"old_state": "none", "new_state": "washing", "trigger": ["wash"]},
                        {"old_state": "washing", "new_state": "drying", "trigger": ["dry"]},
                        {"old_state": "drying", "new_state": "none", "trigger": ["stop"]},
                    ]
                ),
                broken={},
            ),
            transitions=[
                {"old_state": "off", "new_state": "on", "trigger": ["turn_on", "switch"]},
                {"old_state": "on", "new_state": "off", "trigger": ["turn_off", "switch"]},
                {"old_state": "*", "new_state": "broken", "trigger": "smash"},
                {"old_state": "broken", "new_state": {"off": {"condition": lambda obj: random.random() > 0.5},
                                                      "on": {}},
                 "trigger": "fix"},
            ]
        )

        class WashingMachine(StatefulObject):
            state = state_machine(**deepcopy(self.machine_config))

        self.object_class = WashingMachine

    def test_switch(self):
        washer = self.object_class()
        self.assertEqual(washer.state, "off")

        washer.switch()
        self.assertEqual(washer.state, "on.none")

        for _ in range(10):
            washer.smash()
            self.assertEqual(washer.state, "broken")

            washer.fix()
            self.assertIn(washer.state, ("on.none", "off"))

    def test_machine_errors(self):
        config = deepcopy(self.machine_config)
        Path("transitions.3.new_state.off.condition").set_in(config, ())
        with self.assertRaises(MachineError):
            state_machine(**config)

        config = deepcopy(self.machine_config)
        Path("transitions.3.new_state.off").set_in(config, {})
        with self.assertRaises(MachineError):
            state_machine(**config)


class TestCallback(unittest.TestCase):

    def setUp(self):
        """called before any individual test method"""
        self.config = dict(
            states={
                "off": {"on_exit": "on_exit"},
                "on": {"on_entry": "on_entry"},
            },
            transitions=[
                {"old_state": "off", "new_state": "on", "trigger": "switch", "on_transfer": "on_transfer",
                 "condition": "condition"},
            ],
        )

        class Radio(StatefulObject):
            """object class fo which the state is managed"""
            state = state_machine(**self.config)

            def __init__(self, testcase):
                super(Radio, self).__init__()
                self.testcase = testcase

            def condition(self, a, **kwargs):
                self.testcase.assertEqual(a, 1)
                return True

            def on_entry(self, b, **kwargs):
                self.testcase.assertEqual(b, 2)

            def on_exit(self, c, **kwargs):
                self.testcase.assertEqual(c, 3)

            def on_transfer(self, d, **kwargs):
                self.testcase.assertEqual(d, 4)

            @state.on_exit('*')
            def on_any_exit(self, e, **kwargs):
                self.testcase.assertEqual(e, 5)

            @state.on_entry('*')
            def on_any_entry(self, f, **kwargs):
                self.testcase.assertEqual(f, 6)

            @contextmanager
            def context_manager(self, g, **kwargs):
                self.testcase.assertEqual(g, 7)
                yield

        self.radio = Radio(self)

    def test_callbacks(self):
        self.radio.switch(a=1, b=2, c=3, d=4, e=5, f=6, g=7, h=None)


class TestMultiState(unittest.TestCase):

    def setUp(self):
        class MoodyColor(StatefulObject):
            color = state_machine(
                states=dict(
                    red={'on_exit': 'on_exit', 'on_entry': 'on_entry'},
                    blue={'on_exit': 'on_exit', 'on_entry': 'on_entry'},
                    green={'on_exit': 'on_exit', 'on_entry': 'on_entry'}
                ),
                transitions=[
                    dict(old_state='red', new_state='blue', trigger=['next', 'change'], on_transfer='on_transfer'),
                    dict(old_state='blue', new_state='green', trigger=['next', 'change'], on_transfer='on_transfer'),
                    dict(old_state='green', new_state='red', trigger=['next', 'change'], on_transfer='on_transfer'),
                ],
            )

            mood = state_machine(
                states=dict(
                    good={'on_exit': 'on_exit', 'on_entry': 'on_entry'},
                    bad={'on_exit': 'on_exit', 'on_entry': 'on_entry'},
                    ugly={'on_exit': 'on_exit', 'on_entry': 'on_entry'}
                ),
                transitions=[
                    dict(old_state='good', new_state='bad', trigger='next', on_transfer='on_transfer'),
                    dict(old_state='bad', new_state='ugly', trigger='next', on_transfer='on_transfer'),
                    dict(old_state='ugly', new_state='good', trigger='next', on_transfer='on_transfer'),
                ],
            )

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.counter = 0
                self.exit_history = []
                self.entry_history = []
                self.transfer_history = []

            def state(self):
                return dict(mood=self.mood,
                            color=self.color)

            @color.on_entry('*')
            def count_calls(self):
                self.counter += 1

            @mood.on_entry('*')
            def count_calls(self):
                self.counter += 1

            def on_exit(self):
                self.exit_history.append(self.state())

            def on_entry(self):
                self.entry_history.append(self.state())

            def on_transfer(self):
                self.transfer_history.append(self.state())

        self.state_class = MoodyColor

    def test_inheritance(self):
        mc = self.state_class()
        assert len(mc._state_machines) == 2

    def test_combines(self):
        moodycolor = self.state_class()
        moodycolor.next()
        assert moodycolor.counter == 2
        assert moodycolor.color == 'blue'
        assert moodycolor.mood == 'bad'
        n = 3
        for _ in range(n):
            moodycolor.next()
        assert moodycolor.counter == 2 + n * 2

    def test_only_color(self):
        moodycolor = self.state_class()
        moodycolor.change()
        assert moodycolor.counter == 1
        assert moodycolor.color == 'blue'
        assert moodycolor.mood == 'good'

    def test_initial(self):
        moodycolor = self.state_class(color='green', mood='ugly')
        assert moodycolor.color == 'green'
        assert moodycolor.mood == 'ugly'
        moodycolor.next()
        assert moodycolor.counter == 2
        assert moodycolor.color == 'red'
        assert moodycolor.mood == 'good'

    def test_trigger_initial(self):
        moodycolor = self.state_class()
        assert moodycolor.color == 'red'
        assert moodycolor.mood == 'good'
        assert moodycolor.entry_history == []
        assert moodycolor.exit_history == []
        moodycolor.trigger_initial()
        assert moodycolor.entry_history == [{'color': 'red', 'mood': 'good'},
                                            {'color': 'red', 'mood': 'good'}]
        assert moodycolor.exit_history == []
        assert moodycolor.counter == 2
        moodycolor.next()
        assert moodycolor.counter == 4
        assert moodycolor.color == 'blue'
        assert moodycolor.mood == 'bad'

    def test_callbacks(self):
        moodycolor = self.state_class()
        moodycolor.next()
        assert moodycolor.exit_history == [{'color': 'red', 'mood': 'good'},
                                           {'color': 'blue', 'mood': 'good'}]  # color already changed
        assert moodycolor.entry_history == [{'color': 'blue', 'mood': 'good'},  # mood did not change yet
                                            {'color': 'blue', 'mood': 'bad'}]
        assert moodycolor.transfer_history == [{'color': 'blue', 'mood': 'good'},
                                               {'color': 'blue', 'mood': 'bad'}]


class TestMultiStateMachine(unittest.TestCase):
    class MultiSome(StatefulObject):
        color = state_machine(
            states=dict(
                red={'on_exit': 'color_callback'},
                blue={'on_exit': 'color_callback'},
                green={'on_exit': 'color_callback'}
            ),
            transitions=[
                dict(old_state='red', new_state='blue', trigger='next'),
                dict(old_state='blue', new_state='green', trigger='next'),
                dict(old_state='green', new_state='red', trigger='next'),
            ],
        )
        mood = state_machine(
            states=dict(
                good={'on_exit': 'mood_callback'},
                bad={'on_exit': 'mood_callback'},
                ugly={'on_exit': 'mood_callback'}
            ),
            transitions=[
                dict(old_state='good', new_state='bad', trigger='next'),
                dict(old_state='bad', new_state='ugly', trigger='next'),
                dict(old_state='ugly', new_state='good', trigger='next'),
            ],
        )

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.history = dict(color=[], mood=[])

        def color_callback(self):
            self.history['color'].append(self.color)

        def mood_callback(self):
            self.history['mood'].append(self.mood)

    def test_transitions(self):
        some = self.MultiSome()
        for _ in range(6):
            some.next()

        assert some.history['color'] == ['red', 'blue', 'green', 'red', 'blue', 'green']
        assert some.history['mood'] == ['good', 'bad', 'ugly', 'good', 'bad', 'ugly']


class TestMultiStateMachineNewConstructors(unittest.TestCase):
    class MultiSome(StatefulObject):
        color = state_machine(
            states=states(
                red=state(on_exit='color_callback'),
                blue=state(on_exit='color_callback'),
                green=state(on_exit='color_callback'),
            ),
            transitions=[
                transition('red', 'blue', trigger='next'),
                transition('blue', 'green', trigger='next'),
                transition('green', 'red', trigger='next'),
            ],
        )
        mood = state_machine(
            states=states(
                good=state(on_exit='mood_callback'),
                bad=state(on_exit='mood_callback'),
                ugly=state(on_exit='mood_callback')
            ),
            transitions=[
                transition('good', 'bad', trigger='next'),
                transition('bad', 'ugly', trigger='next'),
                transition('ugly', 'good', trigger='next'),
            ],
        )

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.history = dict(color=[], mood=[])

        def color_callback(self):
            self.history['color'].append(self.color)

        def mood_callback(self):
            self.history['mood'].append(self.mood)

    def test_transitions(self):
        some = self.MultiSome()
        for _ in range(6):
            some.next()

        assert some.history['color'] == ['red', 'blue', 'green', 'red', 'blue', 'green']
        assert some.history['mood'] == ['good', 'bad', 'ugly', 'good', 'bad', 'ugly']

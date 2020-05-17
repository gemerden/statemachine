import json
import random
import sys
import unittest
from contextlib import contextmanager
from copy import deepcopy

from states import state_machine, StatefulObject, TransitionError, MachineError
from states.machine import has_doubles, replace_in_list

from states.tools import Path

__author__ = "lars van gemerden"


def count_transitions(state):
    return sum(map(len, state.triggering.values()))


class TestTools(unittest.TestCase):

    def test_replace_in_list(self):
        self.assertEqual(replace_in_list([1, 2, 3], 2, [4, 5]), [1, 4, 5, 3])

    def test_has_doubles(self):
        self.assertTrue(has_doubles([1, 2, 3, 2]))
        self.assertFalse(has_doubles([1, 2, 3, 4]))


class SimplestStateMachineTest(unittest.TestCase):

    def setUp(self):
        self.config = dict(
            name="matter machine",
            initial="off",
            states={
                "on": {"info": "not turned off"},
                "off": {"info": "not turned on"},
            },
            transitions=[
                {"old_state": "off", "new_state": "on", "trigger": "switch", "info": "turn the light on"},
                {"old_state": "on", "new_state": "off", "trigger": "switch", "info": "turn the light off"},
            ],
        )
        self.config_copy = deepcopy(self.config)

        self.machine = state_machine(**self.config)

        class LightSwitch(StatefulObject):
            machine = self.machine

        self.light = LightSwitch()

    def test_construction(self):
        """test whether all states, transitions and trigger(s) are in place"""
        self.assertEqual(len(self.machine), 2)
        self.assertEqual(count_transitions(self.machine), 2)
        self.assertEqual(len(self.machine.triggering), 2)

    def test_triggers(self):
        """test the basio trigger functions and the resultig states"""
        self.assertEqual(self.light.state, "off")
        self.light.switch()
        self.assertEqual(self.light.state, "on")
        self.light.switch()
        self.assertEqual(self.light.state, "off")

    def test_info(self):
        self.assertEqual(self.light.machine.sub_states["on"].info, "not turned off")
        self.assertEqual(self.light.machine.triggering[Path("off"), "switch"][0].info, "turn the light on")

    def test_config(self):
        machine_config = self.light.machine.config
        self.assertEqual(machine_config, self.config_copy)


class StateMachineTest(unittest.TestCase):

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

            def inner(obj, **kwrags):
                return min < obj.temperature <= max or self.temperature_ignore

            return inner

        # create a machine based on phase changes of matter (solid, liquid, gas)
        self.machine = state_machine(
            name="matter machine",
            initial="gas",
            states={
               "solid": {"on_entry": [callback], "on_exit": [callback]},
               "liquid": {"on_entry": [callback], "on_exit": [callback]},
               "gas": {"on_entry": [callback], "on_exit": [callback]}
            },
            transitions=[
                {"old_state": "solid", "new_state": "liquid", "trigger": ["melt", "heat"], "on_transfer": [callback],
                 "condition": temp_checker(0, 100)},
                {"old_state": "solid", "new_state": "solid", "trigger": ["dont"], "on_transfer": [callback],
                 "condition": temp_checker(0, 100)},
                {"old_state": "liquid", "new_state": "gas", "trigger": ["evaporate", "heat"], "on_transfer": callback,
                 "condition": temp_checker(100, float("inf"))},
                {"old_state": "gas", "new_state": "liquid", "trigger": ["condense", "cool"], "on_transfer": ["do_callback"],
                 "condition": temp_checker(0, 100)},
                {"old_state": "liquid", "new_state": "solid", "trigger": ["freeze", "cool"], "on_transfer": "do_callback",
                 "condition": temp_checker(-274, 0)}
            ],
            before_any_exit=callback,
            after_any_entry="do_callback"
        )

        class Matter(StatefulObject):
            """object class fo which the state is managed"""
            machine = self.machine

            def __init__(self, name, temperature=0, initial="solid"):
                super(Matter, self).__init__(initial=initial)
                self.name = name
                self.temperature = temperature  # used in tests of condition callback in transition class

            def do_callback(self, **kwargs):
                """used to test callback lookup bu name"""
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

            def __str__(self):
                return self.name + "(%s)" % self.state

        self.object_class = Matter
        self.block = Matter("block")

    def test_construction(self):
        """test whether all states, transitions and trigger(s) are in place"""
        self.assertEqual(len(self.machine), 3)
        self.assertEqual(count_transitions(self.machine), 9)
        self.assertEqual(len(self.machine.triggering), 9)

    def test_states_property(self):
        self.assertEqual(self.machine.states,
                         ['solid', 'liquid', 'gas'])

    def test_triggers_property(self):
        self.assertEqual(self.machine.triggers,
                         {'heat', 'melt', 'dont', 'cool', 'evaporate', 'freeze', 'condense'})

    def test_transitions_property(self):
        self.assertEqual(self.machine.transitions,
                         {('gas', 'liquid'), ('liquid', 'gas'), ('liquid', 'solid'), ('solid', 'liquid'), ('solid', 'solid')})

    def test_initial(self):
        class Dummy(StatefulObject):
            machine = self.machine

        dummy = Dummy()
        self.assertEqual(dummy.state, "gas")

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
        self.block.dont()
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
        self.assertEqual(self.callback_counter, 5)
        self.block.heat()
        self.assertEqual(self.callback_counter, 10)
        self.block.cool()
        self.assertEqual(self.callback_counter, 15)
        self.block.cool()
        self.assertEqual(self.callback_counter, 20)
        self.block.dont()
        self.assertEqual(self.callback_counter, 25)

    def test_condition(self):
        """tests whether the condition callback works: if the condition fails, no transition takes place"""
        self.temperature_ignore = False
        block = self.object_class("block", temperature=-10)

        transfer = block.heat_by(5)
        self.assertEqual(transfer, False)
        self.assertEqual(block.state, "solid")
        self.assertEqual(self.callback_counter, 0)

        transfer = block.heat_by(10)
        self.assertEqual(transfer, True)
        self.assertEqual(block.state, "liquid")
        self.assertEqual(self.callback_counter, 5)

        transfer = block.heat_by(10)
        self.assertEqual(transfer, False)
        self.assertEqual(block.state, "liquid")
        self.assertEqual(self.callback_counter, 5)

        transfer = block.heat_by(100)
        self.assertEqual(transfer, True)
        self.assertEqual(block.state, "gas")
        self.assertEqual(self.callback_counter, 10)

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
            self.object_class("block", initial="plasma")

    def test_machine_errors(self):
        """tests whether double state names, transitions and trigger(s) and non-existing state names are detected"""
        with self.assertRaises(MachineError):
            state_machine(
                name="matter machine",
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
                name="matter machine",
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
                name="matter machine",
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
        with self.assertRaises(AttributeError):
            class A(StatefulObject):
                machine = state_machine(
                    name="matter machine",
                    initial="solid",
                    states={
                        "solid": {},
                        "liquid": {},
                    },
                    transitions=[
                        {"old_state": "solid", "new_state": "liquid", "trigger": "trgr", "condition": "NOT_THERE"},
                    ]
                )

            a = A()
            a.state = "liquid"


class WildcardStateMachineTest(unittest.TestCase):
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
            name="matter machine",
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
            machine = self.machine

            def __init__(self, name, initial="solid"):
                super(Matter, self).__init__(initial=initial)
                self.name = name

            def __str__(self):
                return self.name + "(%s)" % self.state

        self.object_class = Matter

    def test_construction(self):
        """test whether all states, transitions and trigger(s) are in place"""
        self.assertEqual(len(self.machine), 4)
        self.assertEqual(count_transitions(self.machine), 2+2+2+2+4+1)
        self.assertEqual(len(self.machine.triggering), 2+2+2+2+4+1)

    def test_config(self):
        config = repr(self.object_class.machine)
        config = json.loads(config)
        self.assertEqual(Path("transitions.4.old_state").get_in(config), "*")

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
        self.assertEqual(self.callback_counter, 15)

    def test_transition_exceptions(self):
        """tests whether non-existent transitions are detected"""
        block = self.object_class("block")
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
                name="matter machine",
                states={
                    "solid": {},
                    "liquid": {},
                    "gas": {},
                },
                transitions=[
                    {"old_state": "solid", "new_state": "*", "triggers": ["melt"]}
                ]
            )

    def test_double_wildcard(self):
        with self.assertRaises(MachineError):
            machine = state_machine(
                name="matter machine",
                states={
                    "solid": {},
                    "liquid": {},
                },
                transitions=[
                    {"old_state": "*", "new_state": "*", "on_transfer": []},  # all transitions
                ],
            )



class ListedTransitionStateMachineTest(unittest.TestCase):

    def setUp(self):
        self.callback_counter = 0  # rest for every tests; used to count number of callbacks from machine

        def callback(obj, **kwargs):
            """checks whether the object arrives; calback_counter is used to check whether callbacks are all called"""
            self.assertEqual(type(obj), Matter)
            self.callback_counter += 1

        # create a machine based on phase changes of matter (solid, liquid, gas)
        class Matter(StatefulObject):
            """object class fo which the state is managed"""
            machine = state_machine(
                name="matter machine",
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

            def __init__(self, name, initial="solid"):
                super(Matter, self).__init__(initial=initial)
                self.name = name

            def __str__(self):
                return self.name + "(%s)" % self.state

        self.object_class = Matter

    def test_construction(self):
        """test whether all states, transitions and trigger(s) are in place"""
        self.assertEqual(len(self.object_class.machine.sub_states), 3)
        self.assertEqual(len(self.object_class.machine.triggering), 4)
        self.assertEqual(sum(map(len, self.object_class.machine.triggering.values())), 4)

    def test_config(self):
        config = repr(self.object_class.machine)
        config = json.loads(config)
        self.assertEqual(Path("transitions.0.old_state").get_in(config), ["solid", "liquid"])

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
        block = self.object_class("block", initial="gas")
        with self.assertRaises(TransitionError):
            block.zap()


class SwitchedTransitionStateMachineTest(unittest.TestCase):

    def setUp(self):
        class LightSwitch(StatefulObject):
            machine = state_machine(
                name="matter machine",
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
                                                                             "off":{}}},
                ],
                before_any_exit="store_state"
            )

            def __init__(self, initial=None):
                super(LightSwitch, self).__init__(initial=initial)
                self._old_state = None

            def store_state(self):
                self._old_state = self._state

            def was_on(self):
                return str(self._old_state) == "on"

        self.object_class = LightSwitch

    def test_off(self):
        light_switch = self.object_class(initial="off")
        light_switch.smash()
        light_switch.fix()
        self.assertEqual(light_switch.state, "off")

    def test_on(self):
        light_switch = self.object_class(initial="on")
        light_switch.smash()
        light_switch.fix()
        self.assertEqual(light_switch.state, "on")

    def test_machine_error(self):
        with self.assertRaises(MachineError):
            state_machine(
                name="matter machine",
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


class SwitchedDoubleTransitionStateMachineTest(unittest.TestCase):
    good_machine_dict = dict(
        name="lamp",
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
                                                                     "broken":{}}},
            {"old_state": "broken", "new_state": "broken", "trigger": ["leave"]},
        ],
    )
    bad_machine_dict = dict(
        name="lamp",
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
                                                                     "broken":{}}},
            {"old_state": "broken", "new_state": "broken", "trigger": "FIX"},
        ],
    )

    def test_good_double_transition(self):
        class Lamp(StatefulObject):
            machine = state_machine(**deepcopy(self.good_machine_dict))
        self.assertEqual(count_transitions(Lamp.machine), 9)

    def test_bad_double_transition(self):
        with self.assertRaises(MachineError):
            class Lamp(StatefulObject):
                machine = state_machine(**deepcopy(self.bad_machine_dict))

    def test_transitions(self):
        class Lamp(StatefulObject):
            machine = state_machine(**deepcopy(self.good_machine_dict))

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


class NestedStateMachineTest(unittest.TestCase):
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

        def before_any_exit(obj, **kwargs):
            """ will be used to check whether this method will be looked up in super states """
            self.assertEqual(type(obj), WashingMachine)
            self.before_counter += 1

        # create a machine config based on phase changes of matter (solid, liquid, gas)
        self.machine_config = dict(
            name="washing machine",
            initial="off",
            states=dict(
                off=dict(
                    initial="working",
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
                    before_any_exit=before_any_exit
                ),
                on=dict(
                    initial="none",
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
            before_any_exit=before_any_exit
        )

        class WashingMachine(StatefulObject):
            machine = state_machine(**self.machine_config)

        self.object_class = WashingMachine

    def assert_counters(self, exit_counter, entry_counter, before_counter):
        self.assertEqual(self.exit_counter, exit_counter)
        self.assertEqual(self.entry_counter, entry_counter)
        self.assertEqual(self.before_counter, before_counter)

    def test_config(self):

        config = repr(self.object_class.machine)
        config = json.loads(config)
        for path, expected in [("on_exit", "NONE"),
                               ("states.off.initial", "working"),
                               ("states.off.transitions.0.old_state", "working"),
                               ("transitions.0.old_state", "off.working"),
                               ("transitions.3.trigger", ["just_dry_already"]),
                               ("transitions.3.new_state", "on.drying"),
                               ("transitions.3.condition", "NONE"),
                               ("states.off.states.working.on_exit", "states.tests.test_machine.on_exit")]:
            self.assertEqual(Path(path).get_in(config, "NONE"), expected)

    def test_construction(self):
        """test whether all states, transitions and trigger(s) are in place"""
        self.assertEqual(len(self.object_class.machine), 2)
        self.assertEqual(len(self.object_class.machine.triggering), 6)
        child_state = self.object_class.machine["on"]
        self.assertEqual(len(child_state), 3)
        self.assertEqual(len(child_state.triggering), 3)
        child_state = self.object_class.machine["off"]
        self.assertEqual(len(child_state), 2)
        self.assertEqual(len(child_state.triggering), 2)

    def test_len_in_getitem_iter_for_states(self):
        machine = self.object_class.machine
        self.assertEqual(len(machine), 2)
        self.assertTrue("off" in machine)
        self.assertEqual(machine["on"].name, "on")
        self.assertEqual(machine["on"]["drying"].name, "drying")
        child_state = self.object_class.machine["on"]
        self.assertEqual(len(child_state), 3)
        self.assertTrue("washing" in child_state)
        self.assertEqual(child_state["none"].name, "none")
        self.assertEqual(len([s for s in self.object_class.machine]), 2)

    def test_getitem_for_triggers(self):
        machine = self.object_class.machine
        self.assertEqual(machine["on", "switch"][0].old_state, machine["on"])
        self.assertEqual(machine["on", "switch"][0].new_state, machine["off"])
        self.assertEqual(str(machine["on"]["washing", "dry"][0].old_path), "washing")
        self.assertEqual(str(machine["on"]["washing", "dry"][0].new_path), "drying")
        self.assertEqual(str(machine["off.working", "just_dry_already"][0].old_path), "off.working")
        self.assertEqual(str(machine["off.working", "just_dry_already"][0].new_path), "on.drying")

    def test_in_for_transitions(self):
        machine = self.object_class.machine
        self.assertTrue(("off.working", "on.drying") in machine)
        self.assertTrue(("washing", "dry") in machine["on"])
        self.assertTrue(("none", "wash") in machine["on"])

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
        self.assertEqual(str(self.object_class.machine["on"]), "on")
        self.assertEqual(str(self.object_class.machine["on"]["washing"]), "on.washing")

    def test_transition_errors(self):
        washer = self.object_class()
        self.assert_counters(0, 0, 0)

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
        pass


class SwitchedTransitionTest(unittest.TestCase):
    """test the case where transition configuration contains wildcards '*' """

    def setUp(self):
        # create a machine config based on phase changes of matter (solid, liquid, gas)
        self.machine_config = dict(
            name="washing machine",
            initial="off",
            states=dict(
                broken={},
                off={},
                on=dict(
                    initial="none",
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
                )
            ),
            transitions=[
                {"old_state": "off", "new_state": "on", "trigger": ["turn_on", "switch"]},
                {"old_state": "on", "new_state": "off", "trigger": ["turn_off", "switch"]},
                {"old_state": "*", "new_state": "broken", "trigger": "smash"},
                {
                    "old_state": "broken",
                    "new_state": {"off": {"condition": lambda obj: random.random() > 0},
                                  "on": {}},
                    "trigger": "fix"},
            ]
        )

        class WashingMachine(StatefulObject):
            machine = state_machine(**deepcopy(self.machine_config))

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
            self.assertIn(washer.state, ("on", "off"))

    def test_machine_errors(self):
        config = deepcopy(self.machine_config)
        Path("transitions.3.new_state.off.condition").set_in(config, ())
        with self.assertRaises(MachineError):
            state_machine(**config)

        config = deepcopy(self.machine_config)
        Path("transitions.3.new_state.off").set_in(config, {})
        with self.assertRaises(MachineError):
            state_machine(**config)


class ContextManagerTest(unittest.TestCase):

    def setUp(self):
        """called before any individual test method"""

        # create a machine based on phase changes of matter (solid, liquid, gas)

        @contextmanager
        def manager(obj, **kwargs):
            obj.managed = True
            yield
            obj.managed = False

        self.config = dict(
            name="matter machine",
            initial="solid",
            states={
                "solid": {"on_exit": "on_action", "on_entry": "on_action"},
                "liquid": {"on_exit": "on_action", "on_entry": "on_action"},
                "gas": {"on_exit": "on_action", "on_entry": "on_action"}
            },
            transitions=[
                {"old_state": "solid", "new_state": "liquid", "trigger": ["melt", "heat"], "on_transfer": "on_action"},
                {"old_state": "liquid", "new_state": "gas", "trigger": ["evaporate", "heat"], "on_transfer": "on_action"},
                {"old_state": "gas", "new_state": "liquid", "trigger": ["condense", "cool"], "on_transfer": "on_action"},
                {"old_state": "liquid", "new_state": "solid", "trigger": ["freeze", "cool"], "on_transfer": "on_action"}
            ],
            before_any_exit="on_action",
            after_any_entry="on_action",
            context_manager=manager,
        )

        self.machine = state_machine(**deepcopy(self.config))

        class Matter(StatefulObject):
            """object class fo which the state is managed"""
            machine = self.machine

            def __init__(self, testcase):
                super(Matter, self).__init__()
                self.managed = False
                self.testcase = testcase

            def on_action(self, **kwargs):
                self.testcase.assertEqual(self.managed, True)

            @contextmanager
            def object_manager(self, **kwargs):
                self.managed = True
                yield
                self.managed = False

        self.object_class = Matter

    def test_manager(self):
        matter = self.object_class(testcase=self)
        self.assertEqual(matter.managed, False)
        matter.heat()
        self.assertEqual(matter.managed, False)
        matter.heat()
        self.assertEqual(matter.managed, False)
        matter.cool()
        self.assertEqual(matter.managed, False)
        matter.cool()
        self.assertEqual(matter.managed, False)

    def test_manager_in_object(self):
        self.config["context_manager"] = "object_manager"
        self.object_class.machine = state_machine(**deepcopy(self.config))
        matter = self.object_class(testcase=self)
        self.assertEqual(matter.managed, False)
        matter.heat()
        self.assertEqual(matter.managed, False)
        matter.heat()
        self.assertEqual(matter.managed, False)
        matter.cool()
        self.assertEqual(matter.managed, False)
        matter.cool()
        self.assertEqual(matter.managed, False)


class CallbackTest(unittest.TestCase):

    def setUp(self):
        """called before any individual test method"""
        self.machine = state_machine(
            name="washer",
            initial="off",
            states={
                "off": {"on_exit": "on_exit"},
                "on": {"on_entry": "on_entry"},
            },
            transitions=[
                {"old_state": "off", "new_state": "on", "trigger": "switch", "on_transfer": "on_transfer",
                 "condition": "condition"},
            ],
            before_any_exit="before_any_exit",
            after_any_entry="after_any_entry",
            context_manager="context_manager"
        )

        class Radio(StatefulObject):
            """object class fo which the state is managed"""
            machine = self.machine

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

            def before_any_exit(self, e, **kwargs):
                self.testcase.assertEqual(e, 5)

            def after_any_entry(self, f, **kwargs):
                self.testcase.assertEqual(f, 6)

            @contextmanager
            def context_manager(self, g, **kwargs):
                self.testcase.assertEqual(g, 7)
                yield

        self.radio = Radio(self)

    def test_callbacks(self):
        self.radio.switch(a=1, b=2, c=3, d=4, e=5, f=6, g=7, h=None)


class TriggerOverrideTest(unittest.TestCase):

    def setUp(self):
        """called before any individual test method"""

        class LightSwitch(StatefulObject):
            machine = state_machine(
                states={
                    "on": {},
                    "off": {},
                },
                transitions=[
                    {"old_state": "off", "new_state": "on", "trigger": "flick", "condition": "is_night"},
                    # switch only turns on at night
                    {"old_state": "on", "new_state": "off", "trigger": "flick"},
                ],
            )

            def __init__(self, time=0, *args, **kwargs):
                super(LightSwitch, self).__init__(*args, **kwargs)
                self.time = time

            def flick(self, hours, *args, **kwargs):
                self.time = (self.time + hours) % 24  # increment time with hours and start from 0 if >24 (midnight)
                self.machine.trigger(self, "flick", hours=hours, *args, **kwargs)

            def is_night(self, *args, **kwargs):
                return self.time < 6 or self.time > 18

        self.lightswitch_class = LightSwitch

    def test_override(self):
        switch = self.lightswitch_class(time=0, initial="on")
        self.assertTrue(switch.is_night())
        switch.flick(hours=7)  # switch.time == 7
        self.assertTrue(switch.state == "off")
        switch.flick(hours=7)  # switch.time == 14
        self.assertTrue(switch.state == "off")
        switch.flick(hours=7)  # switch.time == 21
        self.assertTrue(switch.time == 21)
        self.assertTrue(switch.state == "on")


class TransitioningTest(unittest.TestCase):

    def setUp(self):
        """called before any individual test method"""
        self.machine = state_machine(
            name="washer",
            initial="off",
            states={
                "off": {},
                "on": {},
            },
            transitions=[
                {"old_state": "off", "new_state": "on", "trigger": "switch", "on_transfer": "raise_error"},
            ],
            context_manager="context_manager"
        )

        class Radio(StatefulObject):
            """object class fo which the state is managed"""
            machine = self.machine

            def __init__(self, testcase):
                super(Radio, self).__init__()
                self.testcase = testcase

            def raise_error(self, context, **kwargs):
                self.testcase.assertEqual(context, "context")
                raise AssertionError

            @contextmanager
            def context_manager(self, item, **kwargs):
                self.testcase.assertEqual(item, "item")
                yield "context"

        self.radio = Radio(self)

    def test_transitioning(self):
        """ mainly tests whether the state is restored when transitioning raises an exception """
        self.assertEqual(self.radio.state, "off")
        with self.assertRaises(AssertionError):
            self.radio.switch(item="item")
        self.assertEqual(self.radio.state, "off")

import json
import random
import unittest
from contextlib import contextmanager
from copy import deepcopy

from statemachine.machine import state_machine, TransitionError, MachineError, StatefulObject
from statemachine.tools import Path

__author__ = "lars van gemerden"

class SimplestStateMachineTest(unittest.TestCase):

    def setUp(self):

        self.config = dict(
                name="matter machine",
                initial="off",
                states=[
                    {"name": "on"},
                    {"name": "off"},
                ],
                transitions=[
                    {"old_state": "off", "new_state": "on", "triggers": "switch"},
                    {"old_state": "on", "new_state": "off", "triggers": "switch"},
                ],
            )

        self.machine = state_machine(**self.config)

        class LightSwitch(StatefulObject):
            machine = self.machine

        self.light = LightSwitch()

    def test_construction(self):
        """test whether all states, transitions and triggers are in place"""
        self.assertEqual(len(self.machine), 2)
        self.assertEqual(len(self.machine.transitions), 2)
        self.assertEqual(len(self.machine.triggering), 2)

    def test_triggers(self):
        """test the basio trigger functions and the resultig states"""
        self.assertEqual(self.light.state, "off")
        self.light.switch()
        self.assertEqual(self.light.state, "on")
        self.light.switch()
        self.assertEqual(self.light.state, "off")

    def test_set_state(self):
        """tests changing states with the state property of StateObject"""
        self.assertEqual(self.light.state, "off")
        self.light.state = "on"
        self.assertEqual(self.light.state, "on")
        self.light.state = "off"
        self.assertEqual(self.light.state, "off")


class StateMachineTest(unittest.TestCase):

    def setUp(self):
        """called before any individual test method"""
        self.callback_counter = 0  # rest for every tests; used to count number of callbacks from machine
        self.temperature_ignore = True  # used to switch condition function on or off

        def callback(obj, **kwrags):
            """checks whether the object arrives; calback_counter is used to check whether callbacks are all called"""
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
            states=[
                {"name": "solid", "on_entry":[callback], "on_exit":[callback]},
                {"name": "liquid", "on_entry": [callback], "on_exit": [callback]},
                {"name": "gas", "on_entry": [callback], "on_exit": [callback]}
            ],
            transitions=[
                {"old_state": "solid", "new_state": "liquid", "triggers": ["melt", "heat"], "on_transfer": [callback], "condition": temp_checker(0, 100)},
                {"old_state": "solid", "new_state": "solid", "triggers": ["dont"], "on_transfer": [callback], "condition": temp_checker(0, 100)},
                {"old_state": "liquid", "new_state": "gas", "triggers": ["evaporate", "heat"], "on_transfer": callback, "condition": temp_checker(100, float("inf"))},
                {"old_state": "gas", "new_state": "liquid", "triggers": ["condense", "cool"], "on_transfer": ["do_callback"], "condition": temp_checker(0, 100)},
                {"old_state": "liquid", "new_state": "solid", "triggers": ["freeze", "cool"], "on_transfer": "do_callback", "condition": temp_checker(-274, 0)}
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
        """test whether all states, transitions and triggers are in place"""
        self.assertEqual(len(self.machine), 3)
        self.assertEqual(len(self.machine.transitions), 5)
        self.assertEqual(len(self.machine.triggering), 9)

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

    def test_set_state(self):
        """tests changing states with the state property of StateObject"""
        self.block.state = "liquid"
        self.assertEqual(self.block.state, "liquid")
        self.block.state = "gas"
        self.assertEqual(self.block.state, "gas")
        self.block.state = "liquid"
        self.assertEqual(self.block.state, "liquid")
        self.block.state = "solid"
        self.assertEqual(self.block.state, "solid")
        self.block.state = "solid"
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
        with self.assertRaises(TransitionError):
            block.state = "gas"
        self.assertEqual(block.state, "solid")

    def test_init_error(self):
        """tests whether a non-existing initial state is detected"""
        with self.assertRaises(TransitionError):
            self.object_class("block", initial="plasma")

    def test_machine_errors(self):
        """tests whether double state names, transitions and triggers and non-existing state names are detected"""
        with self.assertRaises(MachineError):
            state_machine(
                name="matter machine",
                states=[
                    {"name": "solid"},
                    {"name": "solid"},
                ],
                transitions={}
            )
        with self.assertRaises(MachineError):
            state_machine(
                name="matter machine",
                states=[
                    {"name": "solid"},
                    {"name": "liquid"},
                ],
                transitions=[
                    {"old_state": "solid", "new_state": "gas", "triggers": ["melt"]}
                ]
            )
        with self.assertRaises(MachineError):
            state_machine(
                name="matter machine",
                states=[
                    {"name": "solid"},
                    {"name": "liquid"},
                ],
                transitions=[
                    {"old_state": "solid", "new_state": "liquid", "triggers": ["melt"]},
                    {"old_state": "solid", "new_state": "liquid", "triggers": ["melt"]},
                ]
            )
        with self.assertRaises(MachineError):
            state_machine(
                name="matter machine",
                states=[
                    {"name": "solid"},
                    {"name": "liquid"},
                    {"name": "gas"},
                ],
                transitions=[
                    {"old_state": "solid", "new_state": "liquid", "triggers": ["melt"]},
                    {"old_state": "liquid", "new_state": "gas", "triggers": ["evaporate"]},
                    {"old_state": "liquid", "new_state": "solid", "triggers": ["evaporate"]},
                ]
            )
        with self.assertRaises(AttributeError):
            class A(StatefulObject):
                machine = state_machine(
                    name="matter machine",
                    initial="solid",
                    states=[
                        {"name": "solid"},
                        {"name": "liquid"},
                    ],
                    transitions=[
                        {"old_state": "solid", "new_state": "liquid", "condition": "NOT_THERE"},
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
            states=[
                {"name": "solid", "on_entry":[callback], "on_exit":[callback]},
                {"name": "liquid", "on_entry": [callback], "on_exit": [callback]},
                {"name": "gas", "on_entry": [callback], "on_exit": [callback]},
                {"name": "void", "on_entry": [callback], "on_exit": [callback]}
            ],
            transitions=[
                {"old_state": "solid", "new_state": "liquid", "triggers": ["melt", "heat"], "on_transfer": [callback]},
                {"old_state": "liquid", "new_state": "gas", "triggers": ["evaporate", "heat"], "on_transfer": [callback]},
                {"old_state": "gas", "new_state": "liquid", "triggers": ["condense", "cool"], "on_transfer": [callback]},
                {"old_state": "liquid", "new_state": "solid", "triggers": ["freeze", "cool"], "on_transfer": [callback]},
                {"old_state": "*", "new_state": "void", "triggers": ["zap"], "on_transfer": [callback]},
                {"old_state": "void", "new_state": "*", "on_transfer": [callback]}  # no trigger, because triggers would have same name for each state
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
        """test whether all states, transitions and triggers are in place"""
        self.assertEqual(len(self.machine), 4)
        self.assertEqual(len(self.machine.transitions), 4+4+3)
        self.assertEqual(len(self.machine.triggering), 8+4)

    def test_config(self):
        config = repr(self.object_class.machine)
        config = json.loads(config)
        self.assertEqual(Path("transitions.4.old_state").get_in(config), "*")

    def test_triggers(self):
        """test the basio trigger functions and the resultig states"""
        block = self.object_class("block")
        block.zap()
        self.assertEqual(block.state, "void")
        block.state = "gas"
        self.assertEqual(block.state, "gas")
        block.zap()
        self.assertEqual(block.state, "void")

    def test_shared_triggers(self):
        """test the shared trigger functions (same name for multiple transitions) and the resulting states"""
        block = self.object_class("block")
        block.heat()
        self.assertEqual(block.state, "liquid")
        block.heat()
        self.assertEqual(block.state, "gas")

    def test_set_state(self):
        """tests changing states with the state property of StateObject"""
        block = self.object_class("block")
        block.state = "void"
        self.assertEqual(block.state, "void")
        block.state = "gas"
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
        block.state = "liquid"
        self.assertEqual(self.callback_counter, 15)

    def test_transition_exceptions(self):
        """tests whether non-existent transitions are detected"""
        block = self.object_class("block")
        with self.assertRaises(TransitionError):
            block.evaporate()
        with self.assertRaises(TransitionError):
            block.cool()
        with self.assertRaises(TransitionError):
            block.state = "gas"

    def test_machine_errors(self):
        """tests that new_state wildcard transitions cannot have triggers"""
        with self.assertRaises(MachineError):
            state_machine(
                name="matter machine",
                states=[
                    {"name": "solid"},
                    {"name": "liquid"},
                    {"name": "gas"},
                ],
                transitions=[
                    {"old_state": "solid", "new_state": "*", "triggers": ["melt"]}
                ]
            )

    def test_double_wildcard(self):
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
                states=[
                    {"name": "solid"},
                    {"name": "liquid"},
                    {"name": "gas"},
                ],
                transitions=[
                    {"old_state": "*", "new_state": "*", "on_transfer": [callback]},  # all transitions
                ],
            )

            def __init__(self, name, initial="solid"):
                super(Matter, self).__init__(initial=initial)
                self.name = name

            def __str__(self):
                return self.name + "(%s)" % self.state

        # test whether all states, transitions and triggers are in place
        self.assertEqual(len(Matter.machine), 3)
        self.assertEqual(len(Matter.machine.transitions), 9)
        self.assertEqual(len(Matter.machine.triggering), 0)

        # transitions can only be made with state property (wildcards would creae double triggers in this case)
        block = Matter("block")
        block.state = "liquid"
        self.assertEqual(block.state, "liquid")
        block.state = "gas"
        self.assertEqual(block.state, "gas")
        block.state = "liquid"
        self.assertEqual(block.state, "liquid")
        block.state = "solid"
        self.assertEqual(block.state, "solid")


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
                states=[
                    {"name": "solid"},
                    {"name": "liquid"},
                    {"name": "gas"},
                ],
                transitions=[
                    {"old_state": ["solid", "liquid"], "new_state": "gas", "triggers": ["zap"]},
                    {"old_state": "gas", "new_state": ["solid", "liquid"]},
                ],
            )

            def __init__(self, name, initial="solid"):
                super(Matter, self).__init__(initial=initial)
                self.name = name

            def __str__(self):
                return self.name + "(%s)" % self.state

        self.object_class = Matter

    def test_construction(self):
        """test whether all states, transitions and triggers are in place"""
        self.assertEqual(len(self.object_class.machine.sub_states), 3)
        self.assertEqual(len(self.object_class.machine.transitions), 4)
        self.assertEqual(len(self.object_class.machine.triggering), 2)

    def test_config(self):
        config = repr(self.object_class.machine)
        config = json.loads(config)
        self.assertEqual(Path("transitions.0.old_state").get_in(config), ["solid", "liquid"])

    def test_transitions(self):
        """test whether transitions work in this case"""
        block = self.object_class("block")
        block.zap()
        self.assertEqual(block.state, "gas")
        block.state = "solid"
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
                states=[
                    {"name": "on"},
                    {"name": "off"},
                    {"name": "broken"}
                ],
                transitions=[
                    {"old_state": "off", "new_state": "on", "triggers": ["turn_on", "switch"]},
                    {"old_state": "on", "new_state": "off", "triggers": ["turn_off", "switch"]},
                    {"old_state": ["on", "off"], "new_state": "broken", "triggers": "smash"},
                    {"old_state": "broken", "triggers": "fix", "new_states": [{"name": "on", "condition": "was_on"},
                                                                              {"name": "off"}]},
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
                    states=[
                        {"name": "on"},
                        {"name": "off"},
                        {"name": "broken"}
                    ],
                    transitions=[
                        {"old_state": "off", "new_state": "on", "triggers": ["turn_on", "switch"]},
                        {"old_state": "on", "new_state": "off", "triggers": ["turn_off", "switch"]},
                        {"old_state": ["on", "off"], "new_state": "broken", "triggers": "smash"},
                        {"old_state": "broken", "new_state": "off", "triggers": "fix"},  # will first be checked
                        {"old_state": "broken", "new_state": "on", "triggers": "fix", "condition": "was_on"},
                    ],
                )

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
            states=[
                dict(
                    name="off",
                    initial="working",
                    on_entry=on_entry,
                    on_exit=on_exit,
                    states=[
                        {"name": "working", "on_entry": on_entry, "on_exit": on_exit},
                        {"name": "broken", "on_entry": on_entry, "on_exit": on_exit},
                    ],
                    transitions=[
                        {"old_state": "working", "new_state": "broken", "triggers": ["smash"]},
                        {"old_state": "broken", "new_state": "working", "triggers": ["fix"]},
                    ],
                    before_any_exit = before_any_exit
                ),
                dict(
                    name="on",
                    initial="none",
                    on_entry=on_entry,
                    on_exit=on_exit,
                    states=[
                        {"name": "none", "on_entry": on_entry, "on_exit": on_exit},
                        {"name": "washing", "on_entry": on_entry, "on_exit": on_exit},
                        {"name": "drying", "on_entry": on_entry, "on_exit": on_exit},
                    ],
                    transitions=[
                        {"old_state": "none", "new_state": "washing", "triggers": ["wash"]},
                        {"old_state": "washing", "new_state": "drying", "triggers": ["dry"]},
                        {"old_state": "drying", "new_state": "none", "triggers": ["stop"]},
                    ]
                )
            ],
            transitions=[
                {"old_state": "off.working", "new_state": "on", "triggers": ["turn_on", "switch"]},
                {"old_state": "on", "new_state": "off", "triggers": ["turn_off", "switch"]},
                {"old_state": "on", "new_state": "off.broken", "triggers": ["smash"]},
                {"old_state": "off.working", "new_state": "on.drying", "triggers": ["just_dry_already"]},
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
                               ("states.0.name", "off"),
                               ("states.0.states.0.name", "working"),
                               ("transitions.0.old_state", "off.working"),
                               ("transitions.3.triggers", ["just_dry_already"]),
                               ("transitions.3.new_state", "on.drying"),
                               ("transitions.3.condition", "NONE"),
                               ("states.0.states.0.on_exit", "statemachine.tests.test_machine.on_exit"),
                               ("states.0.transitions.0.new_state", "broken")]:
            self.assertEqual(Path(path).get_in(config, "NONE"), expected)

    def test_construction(self):
        """test whether all states, transitions and triggers are in place"""
        self.assertEqual(len(self.object_class.machine), 2)
        self.assertEqual(len(self.object_class.machine.transitions), 4)
        self.assertEqual(len(self.object_class.machine.triggering), 6)
        child_state = self.object_class.machine["on"]
        self.assertEqual(len(child_state), 3)
        self.assertEqual(len(child_state.transitions), 3)
        self.assertEqual(len(child_state.triggering), 3)
        child_state = self.object_class.machine["off"]
        self.assertEqual(len(child_state), 2)
        self.assertEqual(len(child_state.transitions), 2)
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

    def test_getitem_for_transitions(self):
        machine = self.object_class.machine
        self.assertEqual(machine["on", "off"].old_state, machine["on"])
        self.assertEqual(machine["on", "off"].new_state, machine["off"])
        self.assertEqual(str(machine["on"]["washing", "drying"].old_path), "washing")
        self.assertEqual(str(machine["on"]["washing", "drying"].new_path), "drying")
        self.assertEqual(str(machine["off.working", "on.drying"].old_path), "off.working")
        self.assertEqual(str(machine["off.working", "on.drying"].new_path), "on.drying")

    def test_in_for_transitions(self):
        machine = self.object_class.machine
        self.assertTrue(("off.working", "on.drying") in machine)
        self.assertTrue(("washing", "drying") in machine["on"])
        self.assertFalse(("none", "drying") in machine["on"])

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

    def test_set_state(self):
        washer = self.object_class()
        self.assert_counters(0, 0, 0)

        washer.state = "on"
        self.assertEqual(washer.state, "on.none")
        self.assert_counters(2, 2, 2)

        washer.state = "on.washing"
        self.assertEqual(washer.state, "on.washing")
        self.assert_counters(3, 3, 2)

        washer.state = "on.drying"
        self.assertEqual(washer.state, "on.drying")
        self.assert_counters(4, 4, 2)

        washer.state = "off"
        self.assertEqual(washer.state, "off.working")
        self.assert_counters(6, 6, 3)

        washer.state = "on.drying"
        self.assertEqual(washer.state, "on.drying")
        self.assert_counters(8, 8, 5)

        washer.state = "off.working"
        self.assertEqual(washer.state, "off.working")
        self.assert_counters(10, 10, 6)

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

        with self.assertRaises(TransitionError):
            washer.state = "on"
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
            states=[
                dict(
                    name="broken",
                ),
                dict(
                    name="off",
                ),
                dict(
                    name="on",
                    initial="none",
                    states=[
                        {"name": "none"},
                        {"name": "washing"},
                        {"name": "drying"},
                    ],
                    transitions=[
                        {"old_state": "none", "new_state": "washing", "triggers": ["wash"]},
                        {"old_state": "washing", "new_state": "drying", "triggers": ["dry"]},
                        {"old_state": "drying", "new_state": "none", "triggers": ["stop"]},
                    ]
                )
            ],
            transitions=[
                {"old_state": "off", "new_state": "on", "triggers": ["turn_on", "switch"]},
                {"old_state": "on", "new_state": "off", "triggers": ["turn_off", "switch"]},
                {"old_state": "*", "new_state": "broken", "triggers": "smash"},
                {
                    "old_state": "broken",
                    "new_states": [{"name": "off", "condition": lambda obj: random.random() > 0},
                                   {"name": "on"}],
                    "triggers": "fix"},
            ],
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
        Path("transitions.3.new_states.0.condition").set_in(config, ())
        with self.assertRaises(MachineError):
            state_machine(**config)

        config = deepcopy(self.machine_config)
        Path("transitions.3.new_state").set_in(config, "off")
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
            states=[
                {"name": "solid", "on_exit": "on_action", "on_entry": "on_action"},
                {"name": "liquid", "on_exit": "on_action", "on_entry": "on_action"},
                {"name": "gas", "on_exit": "on_action", "on_entry": "on_action"}
            ],
            transitions=[
                {"old_state": "solid", "new_state": "liquid", "triggers": ["melt", "heat"], "on_transfer": "on_action"},
                {"old_state": "liquid", "new_state": "gas", "triggers": ["evaporate", "heat"], "on_transfer": "on_action"},
                {"old_state": "gas", "new_state": "liquid", "triggers": ["condense", "cool"], "on_transfer": "on_action"},
                {"old_state": "liquid", "new_state": "solid", "triggers": ["freeze", "cool"], "on_transfer": "on_action"}
            ],
            before_any_exit="on_action",
            after_any_entry="on_action",
            context_manager=manager,
        )

        self.machine = state_machine(**self.config)

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
        self.object_class.machine = state_machine(**self.config)
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
            states=[
                {"name": "off", "on_exit":"on_exit"},
                {"name": "on", "on_entry": "on_entry"},
            ],
            transitions=[
                {"old_state": "off", "new_state": "on", "triggers": "switch", "on_transfer": "on_transfer", "condition": "condition"},
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
                states=[
                    {"name": "on"},
                    {"name": "off"},
                ],
                transitions=[
                    {"old_state": "off", "new_state": "on", "triggers": "flick", "condition": "is_night"},
                    # switch only turns on at night
                    {"old_state": "on", "new_state": "off", "triggers": "flick"},
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
            states=[
                {"name": "off"},
                {"name": "on"},
            ],
            transitions=[
                {"old_state": "off", "new_state": "on", "triggers": "switch", "on_transfer": "raise_error"},
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


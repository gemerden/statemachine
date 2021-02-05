import json
import random
import unittest

from states import StatefulObject, TransitionError, MachineError
from states.machine import state_machine

from states.tools import Path, states, transition, state, switch, transitions, case, default

__author__ = "lars van gemerden"


def count_transitions(state):
    return sum(map(len, state._triggering.values()))


class TestSimplestStateMachine(unittest.TestCase):

    def setUp(self):
        class Lamp(StatefulObject):
            state = state_machine(states(off=state(info="not turned on"),
                                         on=state(info="not turned off")),
                                  transitions(transition("off", "on", trigger="flip", info="turn the light on"),
                                              transition("on", "off", trigger="flip", info="turn the light off")))

            def __init__(self):
                super().__init__()
                self.on_count = 0
                self.off_count = 0

            @state.on_entry('on')
            def inc_on_count(self, **kwargs):
                self.on_count += 1

            @state.on_entry('off')
            def inc_on_count(self, **kwargs):
                self.off_count += 1

        self.lamp = Lamp()

    def test_setup(self):
        pass

    def test_construction(self):
        """test whether all states, transitions and trigger(s) are in place"""
        self.assertEqual(len(type(self.lamp).state), 2)
        self.assertEqual(count_transitions(type(self.lamp).state), 2)
        self.assertEqual(len(type(self.lamp).state._triggering), 2)

    def test_triggers(self):
        """test the basio trigger functions and the resultig states"""
        self.assertEqual(self.lamp.state, "off")
        self.lamp.flip()
        self.assertEqual(self.lamp.state, "on")
        self.lamp.flip()
        self.assertEqual(self.lamp.state, "off")
        self.lamp.flip().flip()
        self.assertEqual(self.lamp.state, "off")
        self.assertEqual(self.lamp.on_count, 2)
        self.assertEqual(self.lamp.off_count, 2)

    def test_info(self):
        self.assertEqual(type(self.lamp).state._sub_states["on"].info, "not turned off")
        self.assertEqual(type(self.lamp).state._triggering[Path("off"), "flip"][0].info, "turn the light on")


class TestStateMachine(unittest.TestCase):

    def setUp(self):
        """called before any individual test method"""
        self.callback_counter = 0  # rest for every tests; used to count number of callbacks from machine
        self.temperature_ignore = True  # used to switch condition function on or off

        def temp_checker(min, max):
            """some configurable condition function; only in effect when temperature_ignore==False (some tests)"""

            def inner(obj, **ignored):
                return min < obj.temperature <= max or self.temperature_ignore

            return inner

        self.config = dict(
            states=states(
                solid=state(),
                liquid=state(),
                gas=state(),
            ),
            transitions=[
                transition("solid", "liquid", trigger=["melt", "heat"], condition=temp_checker(0, 100)),
                transition("liquid", "gas", trigger=["evaporate", "heat"], condition=temp_checker(100, float("inf"))),
                transition("gas", "liquid", trigger=["condense", "cool"], condition=temp_checker(0, 100)),
                transition("liquid", "solid", trigger=["freeze", "cool"], condition=temp_checker(-274, 0)),
            ],
        )

        class Matter(StatefulObject):
            """object class for which the state is managed"""
            state = state_machine(**self.config)

            def __init__(self, name, temperature=0, state="solid"):
                super(Matter, self).__init__(state=state)
                self.name = name
                self.temperature = temperature  # used in tests of condition callback in transition class
                self.stayed = 0

            @state.on_transfer('gas', 'liquid')
            @state.on_transfer('liquid', 'solid')
            @state.on_entry('*')
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

            @state.on_stay('solid')
            def do_on_stay(self, **kwargs):
                self.stayed += 1

            def __str__(self):
                return self.name + "(%s)" % self.state

        @Matter.state.on_entry('solid', 'liquid', 'gas')
        @Matter.state.on_exit('solid', 'liquid', 'gas')
        @Matter.state.on_stay('solid')
        @Matter.state.on_transfer('solid', 'liquid')
        @Matter.state.on_transfer('liquid', 'gas')
        @Matter.state.on_exit('*')
        def callback(obj, **kwargs):
            """checks whether the object arrives; callback_counter is used to check whether callbacks are all called"""
            self.assertEqual(type(obj), Matter)
            self.callback_counter += 1

        self.object_class = Matter
        self.block = Matter("block")
        self.machine = Matter.state

    def tearDown(self):
        self.temperature_ignore = True

    def test_construction(self):
        """test whether all states, transitions and trigger(s) are in place"""
        self.assertEqual(len(self.machine), 3)
        self.assertEqual(count_transitions(self.machine), 16)
        self.assertEqual(len(self.machine._triggering), 8)

    def test_states_property(self):
        self.assertEqual(self.machine.states,
                         ['solid', 'liquid', 'gas'])

    def test_triggers_property(self):
        self.assertEqual(self.machine.triggers,
                         {'heat', 'melt', 'cool', 'evaporate', 'freeze', 'condense'})

    def test_transitions_property(self):
        self.assertEqual(set(self.machine.transitions),
                         {('gas', 'liquid'), ('liquid', 'gas'), ('liquid', 'solid'),
                          ('solid', 'liquid'), ('solid', 'solid'), ('liquid', 'liquid'), ('gas', 'gas')})

    def test_initial(self):
        class Dummy(StatefulObject):
            state = state_machine(**self.config)

        dummy = Dummy(state='gas')
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

    def test_condition(self):
        """tests whether the condition callback works: if the condition fails, no transition takes place"""
        self.callback_counter = 0
        self.temperature_ignore = False
        block = self.object_class("block", temperature=-10)

        block = block.heat_by(5)
        self.assertEqual(block.state, "solid")
        self.assertEqual(self.callback_counter, 1)  # on_stay('solid')

        block = block.heat_by(10)
        self.assertEqual(block.state, "liquid")
        self.assertEqual(self.callback_counter, 6)  # 5 + 1 from before

        block = block.heat_by(10)
        self.assertEqual(block.state, "liquid")
        self.assertEqual(self.callback_counter, 6)

        block = block.heat_by(100)
        self.assertEqual(block.state, "gas")
        self.assertEqual(self.callback_counter, 11)

    def test_on_stay(self):
        block = self.object_class("block", temperature=-100)
        self.temperature_ignore = False
        self.assertEqual(block.state, "solid")
        block.heat_by(10)
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
        with self.assertRaises(KeyError):
            self.object_class("block", state="plasma")

    def test_machine_errors(self):
        """tests whether double state names, transitions and trigger(s) and non-existing state names are detected"""
        with self.assertRaises(MachineError):
            state_machine(
                states=states(
                    solid=state(),
                    liquid=state(),
                ),
                transitions=[
                    transition("solid", "gas", trigger=["melt"]),
                ]
            )
        with self.assertRaises(MachineError):
            state_machine(
                states=states(
                    solid=state(),
                    liquid=state(),
                ),
                transitions=[
                    transition("solid", "liquid", trigger=["melt"]),
                    transition("solid", "liquid", trigger=["melt"])
                ]
            )
        with self.assertRaises(MachineError):
            state_machine(
                states=states(
                    solid=state(),
                    liquid=state(),
                    gas=state(),
                ),
                transitions=[
                    transition("solid", "liquid", trigger=["melt"]),
                    transition("liquid", "gas", trigger=["evaporate"]),
                    transition("liquid", "solid", trigger=["evaporate"]),
                ]
            )
        with self.assertRaises(AttributeError):
            class A(StatefulObject):
                state = state_machine(
                    states=states(
                        solid=state(),
                        liquid=state(),
                    ),
                    transitions=[
                        transition("solid", "liquid", trigger=['t'], condition="NO"),
                    ]
                )

            a = A()
            a.state = "liquid"


class TestWildcardStateMachine(unittest.TestCase):
    """test the case where transition configuration contains wildcards '*' """

    def setUp(self):
        """called before any individual test method"""
        self.callback_counter = 0  # rest for every tests; used to count number of callbacks from machine

        # create a machine based on phase changes of matter (solid, liquid, gas)

        self.machine = state_machine(
            states(solid=state(),
                   liquid=state(),
                   gas=state(),
                   void=state()),

            transitions(transition('solid', 'liquid', trigger=["melt", "heat"]),
                        transition('liquid', 'gas', trigger=["evaporate", "heat"]),
                        transition('gas', 'liquid', trigger=["condense", "cool"]),
                        transition('liquid', 'solid', trigger=["freeze", "cool"]),
                        transition('*', 'void', trigger=["zap"]),
                        transition('void', 'solid', trigger=["unzap"]))
        )

        class Matter(StatefulObject):
            """object class fo which the state is managed"""
            state = self.machine

            def __init__(self, name, state="solid"):
                super(Matter, self).__init__(state=state)
                self.callback_counter = 0
                self.name = name

            @state.on_exit('*')
            @state.on_entry('*')
            @state.on_transfer('*', '*')
            def callback(obj, **kwargs):
                """checks whether the object arrives; calback_counter is used to check whether callbacks are all called"""
                self.assertEqual(type(obj), Matter)
                self.callback_counter += 1

            def __str__(self):
                return self.name + "(%s)" % self.state

        self.object_class = Matter

    def test_construction(self):
        """test whether all states, transitions and trigger(s) are in place"""
        self.assertEqual(len(self.machine), 4)
        self.assertEqual(count_transitions(self.machine), 2 + 2 + 2 + 2 + 4 + 1)
        self.assertEqual(len(self.machine._triggering), 2 + 2 + 2 + 2 + 4 + 1)

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
                states=states(
                    solid=state(),
                    liquid=state(),
                ),
                transitions=[
                    transition('solid', '*', trigger='melt')
                ]
            )

    def test_double_wildcard(self):
        with self.assertRaises(MachineError):
            state_machine(
                states=states(
                    solid=state(),
                    liquid=state(),
                ),
                transitions=[
                    transition('*', '*', trigger='melt')
                ]
            )



class TestListedTransitionStateMachine(unittest.TestCase):

    def setUp(self):
        self.callback_counter = 0  # rest for every tests; used to count number of callbacks from machine

        # create a machine based on phase changes of matter (solid, liquid, gas)
        class Matter(StatefulObject):
            """object class fo which the state is managed"""
            state = state_machine(
                states(solid=state(),
                       liquid=state(),
                       gas=state()),
                transitions(transition(["solid", "liquid"], 'gas', trigger='zap'),
                            transition("gas", "liquid", trigger='cool'),
                            transition("liquid", "solid", trigger='cool')),
            )

            def __init__(self, name, state="solid"):
                super(Matter, self).__init__(state=state)
                self.callback_counter = 0
                self.name = name

            def callback(self, **kwargs):
                """checks whether the object arrives; calback_counter is used to check whether callbacks are all called"""
                self.callback_counter += 1

            def __str__(self):
                return self.name + "(%s)" % self.state

        self.object_class = Matter
        self.machine = Matter.state

    def test_construction(self):
        """test whether all states, transitions and trigger(s) are in place"""
        self.assertEqual(len(self.machine._sub_states), 3)
        self.assertEqual(len(self.machine._triggering), 4)
        self.assertEqual(sum(map(len, self.machine._triggering.values())), 4)

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
                states=states(on=state(),
                              off=state(),
                              broken=state()),
                transitions=transitions(transition('off', 'on', trigger=["turn_on", "switch"]),
                                        transition('on', 'off', trigger=["turn_off", "switch"]),
                                        transition(["on", "off"], 'broken', trigger="smash"),
                                        transition('broken', switch(case('on','was_on'),
                                                                    default('off')),
                                                   trigger='fix')),
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
                states(
                    on=state(),
                    off=state(),
                    broken=state()),
                transitions(transition('off', 'on', trigger=["turn_on", "switch"]),
                            transition('on', 'off', trigger=["turn_off", "switch"]),
                            transition(["on", "off"], 'broken', trigger="smash"),
                            transition('broken', switch(default('off'),  # wrong order
                                                        case('on', 'was_on')),
                                       trigger='fix'))
            )


class TestSwitchedDoubleTransitionStateMachine(unittest.TestCase):
    def test(self):  # same as in old machine
        pass


class TestNestedStateMachine(unittest.TestCase):
    """test the case where transition configuration contains wildcards '*' """

    def setUp(self):
        """called before any individual test method"""
        # create a machine config based on phase changes of matter (solid, liquid, gas)
        self.machine = state_machine(
            states(off=state(states(working=state(),
                                    broken=state()),
                             transitions(transition('working', 'broken', trigger='smash'),
                                         transition('broken', 'working', trigger='fix'))),
                   on=state(states(waiting=state(),
                                   washing=state(),
                                   drying=state()),
                            transitions(transition('waiting', 'washing', trigger='wash'),
                                        transition('washing', 'drying', trigger='dry'),
                                        transition('drying', 'waiting', trigger='stop')))),
            transitions(transition('off.working', 'on', trigger=["turn_on", "flip"]),
                        transition('on', 'off', trigger=["turn_off", "flip"]),
                        transition(('on.*', 'off'), 'off.broken', trigger=["smash"]),
                        transition('off.working', 'on.drying', trigger=["just_dry_already"]))
        )

        class WashingMachine(StatefulObject):
            state = self.machine

            def __init__(self):
                super().__init__()
                self.exit_counter = 0  # reset for every tests; used to count number of callbacks from machine
                self.entry_counter = 0  # reset for every tests; used to count number of callbacks from machine
                self.before_counter = 0  # reset for every tests; used to count number of callbacks from machine

            @state.on_exit('off.*', 'on.*')
            def on_exit(self, **kwargs):
                """basic check + counts the number of times the object exits a state"""
                self.exit_counter += 1

            @state.on_entry('off.*', 'on.*')
            def on_entry(self, **kwargs):
                """basic check + counts the number of times the object enters a state"""
                self.entry_counter += 1

            @state.on_exit('*')
            def on_any_exit(self, **kwargs):
                """ will be used to check whether this method will be looked up in super states """
                self.before_counter += 1

        self.object_class = WashingMachine

    def assert_counters(self, washer, exit_counter, entry_counter, before_counter):
        self.assertEqual(washer.exit_counter, exit_counter)
        self.assertEqual(washer.entry_counter, entry_counter)
        self.assertEqual(washer.before_counter, before_counter)

    def test_construction(self):
        """test whether all states, transitions and trigger(s) are in place"""
        self.assertEqual(len(self.object_class.state), 2)
        self.assertEqual(len(self.object_class.state._triggering), 12)
        child_state = self.object_class.state["on"]
        self.assertEqual(len(child_state), 3)
        self.assertEqual(len(child_state._triggering), 3)
        child_state = self.object_class.state["off"]
        self.assertEqual(len(child_state), 2)
        self.assertEqual(len(child_state._triggering), 3)

    def test_len_in_getitem_iter_for_states(self):
        machine = self.object_class.state
        self.assertEqual(len(machine), 2)
        self.assertTrue("off" in machine)
        self.assertEqual(machine["on"].name, "on")
        self.assertEqual(machine["on"]["drying"].name, "drying")
        child_state = self.object_class.state["on"]
        self.assertEqual(len(child_state), 3)
        self.assertTrue("washing" in child_state)
        self.assertEqual(child_state["waiting"].name, "waiting")
        self.assertEqual(len([s for s in self.object_class.state]), 2)

    def test_getitem_for_triggers(self):
        machine = self.object_class.state
        self.assertEqual(machine["off.working", "on.waiting"][0].old_state, machine["off"]["working"])
        self.assertEqual(machine["off.working", "on.waiting"][0].new_state, machine["on"]["waiting"])
        self.assertEqual(str(machine["on"]["washing", "drying"][0].old_path), "washing")
        self.assertEqual(str(machine["on"]["washing", "drying"][0].new_path), "drying")
        self.assertEqual(str(machine["off.working", "on.drying"][0].old_path), "off.working")
        self.assertEqual(str(machine["off.working", "on.drying"][0].new_path), "on.drying")

    def test_in_for_transitions(self):
        machine = self.object_class.state
        self.assertTrue(("off.working", "on.drying") in machine)
        self.assertTrue(("washing", "drying") in machine["on"])
        self.assertTrue(("waiting", "washing") in machine["on"])

    def test_triggering(self):
        washer = self.object_class()
        self.assertEqual(washer.state, "off.working")
        self.assert_counters(washer, 0, 0, 0)

        washer.flip()
        self.assertEqual(washer.state, "on.waiting")
        self.assert_counters(washer, 1, 1, 1)

        washer.wash()
        self.assertEqual(washer.state, "on.washing")
        self.assert_counters(washer, 2, 2, 1)

        washer.dry()
        self.assertEqual(washer.state, "on.drying")
        self.assert_counters(washer, 3, 3, 1)

        washer.flip()
        self.assertEqual(washer.state, "off.working")
        self.assert_counters(washer, 4, 4, 2)

        washer.just_dry_already()
        self.assertEqual(washer.state, "on.drying")
        self.assert_counters(washer, 5, 5, 3)

    def test_state_string(self):
        self.assertEqual(str(self.object_class.state["on"]), "on")
        self.assertEqual(str(self.object_class.state["on"]["washing"]), "on.washing")

    def test_transition_errors(self):
        washer = self.object_class()
        self.assert_counters(washer, 0, 0, 0)
        self.assertEqual(washer.state, "off.working")

        with self.assertRaises(TransitionError):
            washer.dry()
        self.assertEqual(washer.state, "off.working")
        self.assert_counters(washer, 0, 0, 0)

        with self.assertRaises(TransitionError):
            washer.fix()
        self.assertEqual(washer.state, "off.working")
        self.assert_counters(washer, 0, 0, 0)

        washer.smash()
        self.assertEqual(washer.state, "off.broken")
        self.assert_counters(washer, 1, 1, 0)

    def test_machine_errors(self):  # TODO
        assert "dry" in self.object_class.__dict__

    # class TestSwitchedTransition(unittest.TestCase):
    #     """test the case where transition configuration contains wildcards '*' """
    #
    #     def setUp(self):
    #         # create a machine config based on phase changes of matter (solid, liquid, gas)
    #         self.machine_config = dict(
    #             states=dict(
    #                 off={},
    #                 on=dict(
    #                     states={
    #                         "waiting": {},
    #                         "washing": {},
    #                         "drying": {},
    #                     },
    #                     transitions=[
    #                         {"old_state": "waiting", "new_state": "washing", "trigger": ["wash"]},
    #                         {"old_state": "washing", "new_state": "drying", "trigger": ["dry"]},
    #                         {"old_state": "drying", "new_state": "waiting", "trigger": ["stop"]},
    #                     ]
    #                 ),
    #                 broken={},
    #             ),
    #             transitions=[
    #                 {"old_state": "off", "new_state": "on", "trigger": ["turn_on", "switch"]},
    #                 {"old_state": "on", "new_state": "off", "trigger": ["turn_off", "switch"]},
    #                 {"old_state": "*", "new_state": "broken", "trigger": "smash"},
    #                 {"old_state": "broken", "new_state": {"off": {"condition": lambda obj: random.random() > 0.5},
    #                                                       "on": {}},
    #                  "trigger": "fix"},
    #             ]
    #         )
    #
    #         class WashingMachine(StatefulObject):
    #             state = StateMachine(**deepcopy(self.machine_config))
    #
    #         self.object_class = WashingMachine
    #
    #     def test_switch(self):
    #         washer = self.object_class()
    #         self.assertEqual(washer.state, "off")
    #
    #         washer.switch()
    #         self.assertEqual(washer.state, "on.waiting")
    #
    #         for _ in range(10):
    #             washer.smash()
    #             self.assertEqual(washer.state, "broken")
    #
    #             washer.fix()
    #             self.assertIn(washer.state, ("on.waiting", "off"))
    #
    #     def test_machine_errors(self):
    #         config = deepcopy(self.machine_config)
    #         Path("transitions.3.new_state.off.condition").set_in(config, ())
    #         with self.assertRaises(MachineError):
    #             StateMachine(**config)
    #
    #         config = deepcopy(self.machine_config)
    #         Path("transitions.3.new_state.off").set_in(config, {})
    #         with self.assertRaises(MachineError):
    #             StateMachine(**config)
    #
    #
    # class TestContextManager(unittest.TestCase):
    #
    #     def setUp(self):
    #         """called before any individual test method"""
    #
    #         # create a machine based on phase changes of matter (solid, liquid, gas)
    #
    #         @contextmanager
    #         def manager(obj, **kwargs):
    #             obj.managed = True
    #             yield
    #             obj.managed = False
    #
    #         self.config = dict(
    #             states={
    #                 "solid": {"on_exit": "on_action", "on_entry": "on_action"},
    #                 "liquid": {"on_exit": "on_action", "on_entry": "on_action"},
    #                 "gas": {"on_exit": "on_action", "on_entry": "on_action"}
    #             },
    #             transitions=[
    #                 {"old_state": "solid", "new_state": "liquid", "trigger": ["melt", "heat"], "on_transfer": "on_action"},
    #                 {"old_state": "liquid", "new_state": "gas", "trigger": ["evaporate", "heat"], "on_transfer": "on_action"},
    #                 {"old_state": "gas", "new_state": "liquid", "trigger": ["condense", "cool"], "on_transfer": "on_action"},
    #                 {"old_state": "liquid", "new_state": "solid", "trigger": ["freeze", "cool"], "on_transfer": "on_action"}
    #             ],
    #             on_any_exit="on_action",
    #             on_any_entry="on_action",
    #             context_manager=manager,
    #         )
    #
    #         class Matter(StatefulObject):
    #             """object class fo which the state is managed"""
    #             state = StateMachine(**deepcopy(self.config))
    #
    #             def __init__(self, testcase):
    #                 super(Matter, self).__init__()
    #                 self.managed = False
    #                 self.testcase = testcase
    #
    #             def on_action(self, **kwargs):
    #                 self.testcase.assertEqual(self.managed, True)
    #
    #             @contextmanager
    #             def object_manager(self, **kwargs):
    #                 self.managed = True
    #                 yield
    #                 self.managed = False
    #
    #         self.object_class = Matter
    #
    #     def test_manager(self):
    #         matter = self.object_class(testcase=self)
    #         self.assertEqual(matter.managed, False)
    #         matter.heat()
    #         self.assertEqual(matter.managed, False)
    #         matter.heat()
    #         self.assertEqual(matter.managed, False)
    #         matter.cool()
    #         self.assertEqual(matter.managed, False)
    #         matter.cool()
    #         self.assertEqual(matter.managed, False)
    #
    #     def test_manager_in_object(self):
    #         self.config["context_manager"] = "object_manager"
    #
    #         class NewMatter(self.object_class):
    #             state = StateMachine(**self.config)
    #
    #         matter = NewMatter(testcase=self)
    #         assert matter.state == "solid"
    #         self.assertEqual(matter.managed, False)
    #         matter.heat()
    #         assert matter.state == "liquid"
    #         self.assertEqual(matter.managed, False)
    #         matter.heat()
    #         assert matter.state == "gas"
    #         self.assertEqual(matter.managed, False)
    #         matter.cool()
    #         self.assertEqual(matter.managed, False)
    #         matter.cool()
    #         self.assertEqual(matter.managed, False)
    #
    #
    # class TestCallback(unittest.TestCase):
    #
    #     def setUp(self):
    #         """called before any individual test method"""
    #         self.config = dict(
    #             states={
    #                 "off": {"on_exit": "on_exit"},
    #                 "on": {"on_entry": "on_entry"},
    #             },
    #             transitions=[
    #                 {"old_state": "off", "new_state": "on", "trigger": "switch", "on_transfer": "on_transfer",
    #                  "condition": "condition"},
    #             ],
    #             on_any_exit="on_any_exit",
    #             on_any_entry="on_any_entry",
    #             context_manager="context_manager"
    #         )
    #
    #         class Radio(StatefulObject):
    #             """object class fo which the state is managed"""
    #             state = StateMachine(**self.config)
    #
    #             def __init__(self, testcase):
    #                 super(Radio, self).__init__()
    #                 self.testcase = testcase
    #
    #             def condition(self, a, **kwargs):
    #                 self.testcase.assertEqual(a, 1)
    #                 return True
    #
    #             def on_entry(self, b, **kwargs):
    #                 self.testcase.assertEqual(b, 2)
    #
    #             def on_exit(self, c, **kwargs):
    #                 self.testcase.assertEqual(c, 3)
    #
    #             def on_transfer(self, d, **kwargs):
    #                 self.testcase.assertEqual(d, 4)
    #
    #             def on_any_exit(self, e, **kwargs):
    #                 self.testcase.assertEqual(e, 5)
    #
    #             def on_any_entry(self, f, **kwargs):
    #                 self.testcase.assertEqual(f, 6)
    #
    #             @contextmanager
    #             def context_manager(self, g, **kwargs):
    #                 self.testcase.assertEqual(g, 7)
    #                 yield
    #
    #         self.radio = Radio(self)
    #
    #     def test_callbacks(self):
    #         self.radio.switch(a=1, b=2, c=3, d=4, e=5, f=6, g=7, h=None)
    #
    #
    # class TestPrepare(unittest.TestCase):
    #
    #     def setUp(self):
    #         """called before any individual test method"""
    #
    #         class LightSwitch(StatefulObject):
    #             state = StateMachine(
    #                 states={
    #                     "on": {},
    #                     "off": {},
    #                 },
    #                 transitions=[
    #                     {"old_state": "off", "new_state": "on", "trigger": "flick", "condition": "is_night"},
    #                     # switch only turns on at night
    #                     {"old_state": "on", "new_state": "off", "trigger": "flick"},
    #                 ],
    #                 prepare = "prepare"
    #             )
    #
    #             def __init__(self, time=0, *args, **kwargs):
    #                 super(LightSwitch, self).__init__(*args, **kwargs)
    #                 self.time = time
    #
    #             def prepare(self, hours, *args, **kwargs):
    #                 self.time = (self.time + hours) % 24  # increment time with hours and start from 0 if >24 (midnight)
    #
    #             def is_night(self, *args, **kwargs):
    #                 return self.time < 6 or self.time > 18
    #
    #         self.lightswitch_class = LightSwitch
    #
    #     def test_override(self):
    #         switch = self.lightswitch_class(time=0, state="on")
    #         self.assertTrue(switch.is_night())
    #         switch.flick(hours=7)  # switch.time == 7
    #         assert switch.time == 7
    #         self.assertTrue(switch.state == "off")
    #         switch.flick(hours=7)  # switch.time == 14
    #         assert switch.time == 14
    #         self.assertTrue(switch.state == "off")
    #         switch.flick(hours=7)  # switch.time == 21
    #         assert switch.time == 21
    #         self.assertTrue(switch.time == 21)
    #         self.assertTrue(switch.state == "on")
    #
    #
    # class TestMultiState(unittest.TestCase):
    #
    #     def setUp(self):
    #         class Colored(StatefulObject):
    #             color = StateMachine(
    #                 states=dict(
    #                     red={'on_exit': 'on_exit', 'on_entry': 'on_entry'},
    #                     blue={'on_exit': 'on_exit', 'on_entry': 'on_entry'},
    #                     green={'on_exit': 'on_exit', 'on_entry': 'on_entry'}
    #                 ),
    #                 transitions=[
    #                     dict(old_state='red', new_state='blue', trigger=['next', 'change'], on_transfer='on_transfer'),
    #                     dict(old_state='blue', new_state='green', trigger=['next', 'change'], on_transfer='on_transfer'),
    #                     dict(old_state='green', new_state='red', trigger=['next', 'change'], on_transfer='on_transfer'),
    #                 ],
    #                 on_any_entry='count_calls'
    #             )
    #
    #         class MoodyColor(Colored):
    #
    #             mood = StateMachine(
    #                 states=dict(
    #                     good={'on_exit': 'on_exit', 'on_entry': 'on_entry'},
    #                     bad={'on_exit': 'on_exit', 'on_entry': 'on_entry'},
    #                     ugly={'on_exit': 'on_exit', 'on_entry': 'on_entry'}
    #                 ),
    #                 transitions=[
    #                     dict(old_state='good', new_state='bad', trigger='next', on_transfer='on_transfer'),
    #                     dict(old_state='bad', new_state='ugly', trigger='next', on_transfer='on_transfer'),
    #                     dict(old_state='ugly', new_state='good', trigger='next', on_transfer='on_transfer'),
    #                 ],
    #                 on_any_entry='count_calls'
    #             )
    #
    #             def __init__(self, *args, **kwargs):
    #                 super().__init__(*args, **kwargs)
    #                 self.counter = 0
    #                 self.exit_history = []
    #                 self.entry_history = []
    #                 self.transfer_history = []
    #
    #             def count_calls(self):
    #                 self.counter += 1
    #
    #             def state(self):
    #                 return dict(mood=self.mood,
    #                             color=self.color)
    #
    #             def on_exit(self):
    #                 self.exit_history.append(self.state())
    #
    #             def on_entry(self):
    #                 self.entry_history.append(self.state())
    #
    #             def on_transfer(self):
    #                 self.transfer_history.append(self.state())
    #
    #         self.state_class = MoodyColor
    #
    #     def test_inheritance(self):
    #         mc = self.state_class()
    #         assert len(mc._state_machines) == 2
    #
    #     def test_combines(self):
    #         moodycolor = self.state_class()
    #         moodycolor.next()
    #         assert moodycolor.counter == 2
    #         assert moodycolor.color == 'blue'
    #         assert moodycolor.mood == 'bad'
    #         n = 3
    #         for _ in range(n):
    #             moodycolor.next()
    #         assert moodycolor.counter == 2 + n*2
    #
    #     def test_only_color(self):
    #         moodycolor = self.state_class()
    #         moodycolor.change()
    #         assert moodycolor.counter == 1
    #         assert moodycolor.color == 'blue'
    #         assert moodycolor.mood == 'good'
    #
    #     def test_initial(self):
    #         moodycolor = self.state_class(color='green', mood='ugly')
    #         assert moodycolor.color == 'green'
    #         assert moodycolor.mood == 'ugly'
    #         moodycolor.next()
    #         assert moodycolor.counter == 2
    #         assert moodycolor.color == 'red'
    #         assert moodycolor.mood == 'good'
    #
    #     def test_trigger_initial(self):
    #         moodycolor = self.state_class()
    #         assert moodycolor.color == 'red'
    #         assert moodycolor.mood == 'good'
    #         moodycolor.trigger_initial()
    #         assert moodycolor.entry_history == [{'color': 'red', 'mood': 'good'},
    #                                             {'color': 'red', 'mood': 'good'}]
    #         assert moodycolor.counter == 2
    #         moodycolor.next()
    #         assert moodycolor.counter == 4
    #         assert moodycolor.color == 'blue'
    #         assert moodycolor.mood == 'bad'
    #
    #     def test_callbacks(self):
    #         moodycolor = self.state_class()
    #         moodycolor.next()
    #         assert moodycolor.exit_history == [{'color': 'red', 'mood': 'good'},
    #                                            {'color': 'blue', 'mood': 'good'}]  # color already changed
    #         assert moodycolor.entry_history == [{'color': 'blue', 'mood': 'good'},  # mood did not change yet
    #                                             {'color': 'blue', 'mood': 'bad'}]
    #         assert moodycolor.transfer_history == [{'color': 'red', 'mood': 'good'},
    #                                                {'color': 'blue', 'mood': 'good'}]
    #
    #
    # class TestTransitioning(unittest.TestCase):
    #
    #     def setUp(self):
    #         """called before any individual test method"""
    #         self.config = dict(
    #             states={
    #                 "off": {},
    #                 "on": {},
    #             },
    #             transitions=[
    #                 {"old_state": "off", "new_state": "on", "trigger": "switch", "on_transfer": "raise_error"},
    #             ],
    #             context_manager="context_manager"
    #         )
    #
    #         class Radio(StatefulObject):
    #             """object class fo which the state is managed"""
    #             state = StateMachine(**self.config)
    #
    #             def __init__(self, testcase):
    #                 super(Radio, self).__init__()
    #                 self.testcase = testcase
    #
    #             def raise_error(self, context, **kwargs):
    #                 self.testcase.assertEqual(context, "context")
    #                 raise AssertionError
    #
    #             @contextmanager
    #             def context_manager(self, item, **kwargs):
    #                 self.testcase.assertEqual(item, "item")
    #                 yield "context"
    #
    #         self.radio = Radio(self)
    #
    #     def test_transitioning(self):
    #         """ mainly tests whether the state is restored when transitioning raises an exception """
    #         self.assertEqual(self.radio.state, "off")
    #         with self.assertRaises(AssertionError):
    #             self.radio.switch(item="item")
    #         self.assertEqual(self.radio.state, "off")
    #
    #
    # class TestMultiStateMachine(unittest.TestCase):
    #
    #     class MultiSome(StatefulObject):
    #
    #         color = StateMachine(
    #             states=dict(
    #                 red={'on_exit': 'color_callback'},
    #                 blue={'on_exit': 'color_callback'},
    #                 green={'on_exit': 'color_callback'}
    #             ),
    #             transitions=[
    #                 dict(old_state='red', new_state='blue', trigger='next'),
    #                 dict(old_state='blue', new_state='green', trigger='next'),
    #                 dict(old_state='green', new_state='red', trigger='next'),
    #             ],
    #         )
    #         mood = StateMachine(
    #             states=dict(
    #                 good={'on_exit': 'mood_callback'},
    #                 bad={'on_exit': 'mood_callback'},
    #                 ugly={'on_exit': 'mood_callback'}
    #             ),
    #             transitions=[
    #                 dict(old_state='good', new_state='bad', trigger='next'),
    #                 dict(old_state='bad', new_state='ugly', trigger='next'),
    #                 dict(old_state='ugly', new_state='good', trigger='next'),
    #             ],
    #         )
    #
    #         def __init__(self, *args, **kwargs):
    #             super().__init__(*args, **kwargs)
    #             self.history = dict(color=[], mood=[])
    #
    #         def color_callback(self):
    #             self.history['color'].append(self.color)
    #
    #         def mood_callback(self):
    #             self.history['mood'].append(self.mood)
    #
    #     def test_transitions(self):
    #         some = self.MultiSome()
    #         for _ in range(6):
    #             some.next()
    #
    #         assert some.history['color'] == ['red', 'blue', 'green', 'red', 'blue', 'green']
    #         assert some.history['mood'] == ['good', 'bad', 'ugly', 'good', 'bad', 'ugly']
    #
    #
    # class TestMultiStateMachineNewConstructors(unittest.TestCase):
    #
    #     class MultiSome(StatefulObject):
    #
    #         color = StateMachine(
    #             states=states(
    #                 red=state(on_exit='color_callback'),
    #                 blue=state(on_exit='color_callback'),
    #                 green=state(on_exit='color_callback'),
    #             ),
    #             transitions=[
    #                 transition('red', 'blue', trigger='next'),
    #                 transition('blue', 'green', trigger='next'),
    #                 transition('green', 'red', trigger='next'),
    #             ],
    #         )
    #         mood = StateMachine(
    #             states=states(
    #                 good=state(on_exit='mood_callback'),
    #                 bad=state(on_exit='mood_callback'),
    #                 ugly=state(on_exit='mood_callback')
    #             ),
    #             transitions=[
    #                 transition('good', 'bad', trigger='next'),
    #                 transition('bad', 'ugly', trigger='next'),
    #                 transition('ugly', 'good', trigger='next'),
    #             ],
    #         )
    #
    #         def __init__(self, *args, **kwargs):
    #             super().__init__(*args, **kwargs)
    #             self.history = dict(color=[], mood=[])
    #
    #         def color_callback(self):
    #             self.history['color'].append(self.color)
    #
    #         def mood_callback(self):
    #             self.history['mood'].append(self.mood)
    #
    #     def test_transitions(self):
    #         some = self.MultiSome()
    #         for _ in range(6):
    #             some.next()
    #
    #         assert some.history['color'] == ['red', 'blue', 'green', 'red', 'blue', 'green']
    #         assert some.history['mood'] == ['good', 'bad', 'ugly', 'good', 'bad', 'ugly']
    #
    #
    #
    #
    # if __name__ == '__main__':
    #     unittest.main()

import unittest

from statemachine.machine import StateObject, StateMachine, TransitionError, MachineError


__author__ = "lars van gemerden"


class StateMachineTest(unittest.TestCase):

    def setUp(self):
        """called before any individual test method"""
        self.callback_counter = 0  # rest for every tests; used to count number of callbacks from machine
        self.temperature_ignore = True  # used to switch condition function on or off

        def callback(obj, *args, **kwrags):
            """checks whether the object arrives; calback_counter is used to check whether callbacks are all called"""
            self.assertEqual(type(obj), Matter)
            self.callback_counter += 1

        def temp_checker(min, max):
            """some configurable condition function; only in effect when temperature_ignore==False (some tests)"""
            def inner(obj, *args, **kwrags):
                return min < obj.temperature <= max or self.temperature_ignore
            return inner

        # create a machine based on phase changes of matter (solid, liquid, gas)
        self.machine = StateMachine(
            name="matter machine",
            initial="gas",
            states=[
                {"name": "solid", "on_entry":[callback], "on_exit":[callback]},
                {"name": "liquid", "on_entry": [callback], "on_exit": [callback]},
                {"name": "gas", "on_entry": [callback], "on_exit": [callback]}
            ],
            transitions=[
                {"old_state": "solid", "new_state": "liquid", "triggers": ["melt", "heat"], "on_transfer": [callback], "condition": temp_checker(0, 100)},
                {"old_state": "liquid", "new_state": "gas", "triggers": ["evaporate", "heat"], "on_transfer": callback, "condition": temp_checker(100, float("inf"))},
                {"old_state": "gas", "new_state": "liquid", "triggers": ["condense", "cool"], "on_transfer": ["do_callback"], "condition": temp_checker(0, 100)},
                {"old_state": "liquid", "new_state": "solid", "triggers": ["freeze", "cool"], "on_transfer": "do_callback", "condition": temp_checker(-274, 0)}
            ],
            before_any_exit=callback,
            after_any_entry="do_callback"
        )

        class Matter(StateObject):
            """object class fo which the state is managed"""
            machine = self.machine

            def __init__(self, name, temperature=0, initial="solid"):
                super(Matter, self).__init__(initial=initial)
                self.name = name
                self.temperature = temperature  # used in tests of condition callback in transition class

            def do_callback(self, *args, **kwargs):
                """used to test callback lookup bu name"""
                callback(self, *args, **kwargs)

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

    def test_construction(self):
        """test whether all states, transitions and triggers are in place"""
        self.assertEqual(len(self.machine), 3)
        self.assertEqual(len(self.machine.transitions), 4)
        self.assertEqual(len(self.machine.triggering), 8)

    def test_initial(self):
        class Dummy(StateObject):
            machine = self.machine
        dummy = Dummy()
        self.assertEqual(dummy.state, "gas")

    def test_triggers(self):
        """test the basio trigger functions and the resultig states"""
        block = self.object_class("block")
        block.melt()
        self.assertEqual(block.state, "liquid")
        block.evaporate()
        self.assertEqual(block.state, "gas")
        block.condense()
        self.assertEqual(block.state, "liquid")
        block.freeze()
        self.assertEqual(block.state, "solid")

    def test_shared_triggers(self):
        """test the shared trigger functions (same name for multiple transitions) and the resulting states"""
        block = self.object_class("block")
        block.heat()
        self.assertEqual(block.state, "liquid")
        block.heat()
        self.assertEqual(block.state, "gas")
        block.cool()
        self.assertEqual(block.state, "liquid")
        block.cool()
        self.assertEqual(block.state, "solid")

    def test_set_state(self):
        """tests changing states with the state property of StateObject"""
        block = self.object_class("block")
        block.state = "liquid"
        self.assertEqual(block.state, "liquid")
        block.state = "gas"
        self.assertEqual(block.state, "gas")
        block.state = "liquid"
        self.assertEqual(block.state, "liquid")
        block.state = "solid"
        self.assertEqual(block.state, "solid")

    def test_callback(self):
        """tests whether all callbacks are called during transitions"""
        block = self.object_class("block")
        block.melt()
        self.assertEqual(self.callback_counter, 5)
        block.heat()
        self.assertEqual(self.callback_counter, 10)
        block.cool()
        self.assertEqual(self.callback_counter, 15)

    def test_condition(self):
        """tests whether the condition callback works: if the condition fails, no transition takes place"""
        self.temperature_ignore = False
        block = self.object_class("block", temperature=-10)

        trans = block.heat_by(5)
        self.assertEqual(trans, False)
        self.assertEqual(block.state, "solid")
        self.assertEqual(self.callback_counter, 0)

        trans = block.heat_by(10)
        self.assertEqual(trans, True)
        self.assertEqual(block.state, "liquid")
        self.assertEqual(self.callback_counter, 5)

        trans = block.heat_by(10)
        self.assertEqual(trans, False)
        self.assertEqual(block.state, "liquid")
        self.assertEqual(self.callback_counter, 5)

        trans = block.heat_by(100)
        self.assertEqual(trans, True)
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
        with self.assertRaises(TransitionError):
            block.state = "solid"

    def test_init_error(self):
        """tests whether a non-existing initial state is detected"""
        with self.assertRaises(ValueError):
            self.object_class("block", initial="plasma")

    def test_machine_errors(self):
        """tests whether double state names, transitions and triggers and non-existing state names are detected"""
        with self.assertRaises(MachineError):
            StateMachine(
                name="matter machine",
                states=[
                    {"name": "solid"},
                    {"name": "solid"},
                ],
                transitions={}
            )
        with self.assertRaises(MachineError):
            StateMachine(
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
            StateMachine(
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
            StateMachine(
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
            class A(StateObject):
                machine = StateMachine(
                    name="matter machine",
                    initial="solid",
                    states=[
                        {"name": "solid"},
                        {"name": "liquid"},
                    ],
                    transitions=[
                        {"old_state": "solid", "new_state": "liquid", "condition": "not_there"},
                    ]
                )

            a = A()
            a.state = "liquid"


class WildcardStateMachineTest(unittest.TestCase):
    """test the case where transition configuration contains wildcards '*' """
    def setUp(self):
        """called before any individual test method"""
        self.callback_counter = 0  # rest for every tests; used to count number of callbacks from machine

        def callback(obj, *args, **kwargs):
            """checks whether the object arrives; calback_counter is used to check whether callbacks are all called"""
            self.assertEqual(type(obj), Matter)
            self.callback_counter += 1

        # create a machine based on phase changes of matter (solid, liquid, gas)
        self.machine = StateMachine(
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

        class Matter(StateObject):
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
        self.assertEqual(len(self.machine.transitions), 4+3+3)
        self.assertEqual(len(self.machine.triggering), 8+3)

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
        """tests that to wildcard transitions cannot have triggers"""
        with self.assertRaises(MachineError):
            StateMachine(
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

        def callback(obj, *args, **kwargs):
            """checks whether the object arrives; calback_counter is used to check whether callbacks are all called"""
            self.assertEqual(type(obj), Matter)
            self.callback_counter += 1

        # create a machine based on phase changes of matter (solid, liquid, gas)
        class Matter(StateObject):
            """object class fo which the state is managed"""
            machine = StateMachine(
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
        self.assertEqual(len(Matter.machine.transitions), 6)
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

        def callback(obj, *args, **kwargs):
            """checks whether the object arrives; calback_counter is used to check whether callbacks are all called"""
            self.assertEqual(type(obj), Matter)
            self.callback_counter += 1

        # create a machine based on phase changes of matter (solid, liquid, gas)
        class Matter(StateObject):
            """object class fo which the state is managed"""
            machine = StateMachine(
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

        class LightSwitch(StateObject):

            machine = StateMachine(
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
                    {"old_state": "broken", "new_state": "on", "triggers": "fix", "condition": "was_on"},
                    {"old_state": "broken", "new_state": "off", "triggers": "fix"},
                ],
            )

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
            StateMachine(
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
        self.callback_counter = 0  # rest for every tests; used to count number of callbacks from machine

        def callback(obj, *args, **kwargs):
            """checks whether the object arrives; calback_counter is used to check whether callbacks are all called"""
            self.assertEqual(type(obj), WashingMachine)
            self.callback_counter += 1

        # create a machine based on phase changes of matter (solid, liquid, gas)
        class WashingMachine(StateObject):

            machine = StateMachine(
                name="washing machine",
                initial="off",
                states=[
                    dict(
                        name="off",
                        initial="working",
                        states=[
                            {"name": "working", "on_entry": callback, "on_exit": callback},
                            {"name": "broken", "on_entry": callback, "on_exit": callback},
                        ],
                        transitions=[
                            {"old_state": "working", "new_state": "broken", "triggers": ["smash"], "on_transfer": callback},
                            {"old_state": "broken", "new_state": "working", "triggers": ["fix"], "on_transfer": callback},
                        ]
                    ),
                    dict(
                        name="on",
                        initial="none",
                        states=[
                            {"name": "none", "on_entry": callback, "on_exit": callback},
                            {"name": "washing", "on_entry": callback, "on_exit": callback},
                            {"name": "drying", "on_entry": callback, "on_exit": callback},                            
                        ],
                        transitions=[
                            {"old_state": "none", "new_state": "washing", "triggers": ["wash"], "on_transfer": callback},
                            {"old_state": "washing", "new_state": "drying", "triggers": ["dry"], "on_transfer": callback},    
                            {"old_state": "drying", "new_state": "none", "triggers": ["stop"], "on_transfer": callback},    
                        ]
                    )
                ],
                transitions=[
                    {"old_state": "off.working", "new_state": "on", "triggers": ["turn_on", "switch"]},
                    {"old_state": "on", "new_state": "off", "triggers": ["turn_off", "switch"]},
                    {"old_state": "on", "new_state": "off.broken", "triggers": ["smash"]},
                    {"old_state": "off.working", "new_state": "on.drying", "triggers": ["just_dry_already"]},
                ],
            )

        self.object_class = WashingMachine
        
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
        self.assertEqual(machine["on", "off"].old_states[0], machine["on"])
        self.assertEqual(machine["on", "off"].new_states[0], machine["off"])
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
        washer.switch()
        self.assertEqual(washer.state, "on.none")
        washer.wash()
        self.assertEqual(washer.state, "on.washing")
        washer.dry()
        self.assertEqual(washer.state, "on.drying")
        washer.switch()
        self.assertEqual(washer.state, "off.working")
        washer.just_dry_already()
        self.assertEqual(washer.state, "on.drying")

    def test_set_state(self):
        washer = self.object_class()
        washer.state = "on"
        self.assertEqual(washer.state, "on.none")
        washer.state = "on.washing"
        self.assertEqual(washer.state, "on.washing")
        washer.state = "on.drying"
        self.assertEqual(washer.state, "on.drying")
        washer.state = "off"
        self.assertEqual(washer.state, "off.working")
        washer.state = "on.drying"
        self.assertEqual(washer.state, "on.drying")
        washer.state = "off.working"
        self.assertEqual(washer.state, "off.working")

    def test_state_string(self):
        self.assertEqual(str(self.object_class.machine["on"]), "on")
        self.assertEqual(str(self.object_class.machine["on"]["washing"]), "on.washing")





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
            initial="gas",
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

    def test_setup(self):
        """test whether all states, transitions and triggers are in place"""
        self.assertEqual(len(self.machine.states), 3)
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

    def test_setup(self):
        """test whether all states, transitions and triggers are in place"""
        self.assertEqual(len(self.machine.states), 4)
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
        self.assertEqual(len(Matter.machine.states), 3)
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

    def test_setup(self):
        """test whether all states, transitions and triggers are in place"""
        self.assertEqual(len(self.object_class.machine.states), 3)
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
                    {"old_state": ["on", "off"], "new_state": "broken", "triggers": "hammer"},
                    {"old_state": "broken", "new_state": "on", "triggers": "fix", "condition": "was_on"},
                    {"old_state": "broken", "new_state": "off", "triggers": "fix"},
                ],
            )

            def was_on(self):
                return self._old_state == "on"

        self.object_class = LightSwitch

    def test_off(self):
        light_switch = self.object_class(initial="off")
        light_switch.hammer()
        light_switch.fix()
        self.assertEqual(light_switch.state, "off")

    def test_on(self):
        light_switch = self.object_class(initial="on")
        light_switch.hammer()
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
                        {"old_state": ["on", "off"], "new_state": "broken", "triggers": "hammer"},
                        {"old_state": "broken", "new_state": "off", "triggers": "fix"},  # will first be checked
                        {"old_state": "broken", "new_state": "on", "triggers": "fix", "condition": "was_on"},
                    ],
                )


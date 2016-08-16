import unittest

from statemachine.machine import BaseStateObject, StateMachine, TransitionError, MachineError

__author__ = "lars van gemerden"


class StateMachineTest(unittest.TestCase):

    def setUp(self):
        """called before any individual test method"""
        self.callback_counter = 0  # rest for every tests; used to count number of callbacks from machine
        self.temperature_ignore = True  # used to switch condition function on or off

        def callback(obj, old_state, new_state):
            """checks whether the object arrives; calback_counter is used to check whether callbacks are all called"""
            self.assertEqual(type(obj), Matter)
            self.callback_counter += 1

        def temp_checker(min, max):
            """some configurable condition function; only in effect when temperature_ignore==False (some tests)"""
            def inner(obj, old_state, new_state):
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
                {"old_state": "liquid", "new_state": "gas", "triggers": ["evaporate", "heat"], "on_transfer": [callback], "condition": temp_checker(100, 10000)},
                {"old_state": "gas", "new_state": "liquid", "triggers": ["condense", "cool"], "on_transfer": [callback], "condition": temp_checker(0, 100)},
                {"old_state": "liquid", "new_state": "solid", "triggers": ["freeze", "cool"], "on_transfer": [callback], "condition": temp_checker(-273, 0)}
            ],
            before_any_exit=callback,
            after_any_entry=callback
        )

        class Matter(BaseStateObject):
            """object class fo which the state is managed"""
            machine = self.machine

            def __init__(self, name, temperature=0):
                super(Matter, self).__init__(initial="solid")
                self.name = name
                self.temperature = temperature  # used in tests of condition callback in transition class

            def heat_by(self, delta):
                """used to check condition on transition"""
                self.temperature += delta
                self.heat()

            def cool_by(self, delta):
                """used to check condition on transition"""
                self.temperature -= delta
                self.cool()

            def __str__(self):
                return self.name + "(%s)" % self.state

        self.object_class = Matter

    def test_setup(self):
        """test whether all states, transitions and triggers are in place"""
        self.assertEqual(len(self.machine.states), 3)
        self.assertEqual(len(self.machine.transitions), 4)
        self.assertEqual(len(self.machine.triggers), 8)

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
        """tests changing states with the state property of BaseStateObject"""
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

        block.heat_by(5)
        self.assertEqual(block.state, "solid")
        self.assertEqual(self.callback_counter, 0)
        block.heat_by(10)
        self.assertEqual(block.state, "liquid")
        self.assertEqual(self.callback_counter, 5)
        block.heat_by(10)
        self.assertEqual(block.state, "liquid")
        self.assertEqual(self.callback_counter, 5)
        block.heat_by(100)
        self.assertEqual(block.state, "gas")
        self.assertEqual(self.callback_counter, 10)

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


class WildcardStateMachineTest(unittest.TestCase):
    """test the case where transition configuration contains wildcards '*' """
    def setUp(self):
        """called before any individual test method"""
        self.callback_counter = 0  # rest for every tests; used to count number of callbacks from machine

        def callback(obj, old_state, new_state):
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

        class Matter(BaseStateObject):
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
        self.assertEqual(len(self.machine.triggers), 8+3)

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
        """tests changing states with the state property of BaseStateObject"""
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

        def callback(obj, old_state, new_state):
            """checks whether the object arrives; calback_counter is used to check whether callbacks are all called"""
            self.assertEqual(type(obj), Matter)
            self.callback_counter += 1

        # create a machine based on phase changes of matter (solid, liquid, gas)
        class Matter(BaseStateObject):
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
        self.assertEqual(len(Matter.machine.triggers), 0)

        # transitions can only be made with state property (wildcards would creae double triggers in this case)
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

        with self.assertRaises(TransitionError):
            block.state = "gas"



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
        lump = self.object_class("lump")
        lump.melt()
        self.assertEqual(lump.state, "liquid")
        lump.evaporate()
        self.assertEqual(lump.state, "gas")
        lump.condense()
        self.assertEqual(lump.state, "liquid")
        lump.freeze()
        self.assertEqual(lump.state, "solid")

    def test_shared_triggers(self):
        """test the shared trigger functions (same name for multiple transitions) and the resulting states"""
        lump = self.object_class("lump")
        lump.heat()
        self.assertEqual(lump.state, "liquid")
        lump.heat()
        self.assertEqual(lump.state, "gas")
        lump.cool()
        self.assertEqual(lump.state, "liquid")
        lump.cool()
        self.assertEqual(lump.state, "solid")

    def test_set_state(self):
        """tests changing states with the state property of BaseStateObject"""
        lump = self.object_class("lump")
        lump.state = "liquid"
        self.assertEqual(lump.state, "liquid")
        lump.state = "gas"
        self.assertEqual(lump.state, "gas")
        lump.state = "liquid"
        self.assertEqual(lump.state, "liquid")
        lump.state = "solid"
        self.assertEqual(lump.state, "solid")
        lump.state = "solid"
        self.assertEqual(lump.state, "solid")

    def test_callback(self):
        """tests whether all callbacks are called during transitions"""
        lump = self.object_class("lump")
        lump.melt()
        self.assertEqual(self.callback_counter, 5)
        lump.heat()
        self.assertEqual(self.callback_counter, 10)
        lump.cool()
        self.assertEqual(self.callback_counter, 15)

    def test_condition(self):
        """tests whether the condition callback works: if the condition fails, no transition takes place"""
        self.temperature_ignore = False
        lump = self.object_class("lump", temperature=-10)

        lump.heat_by(5)
        self.assertEqual(lump.state, "solid")
        self.assertEqual(self.callback_counter, 0)
        lump.heat_by(10)
        self.assertEqual(lump.state, "liquid")
        self.assertEqual(self.callback_counter, 5)
        lump.heat_by(10)
        self.assertEqual(lump.state, "liquid")
        self.assertEqual(self.callback_counter, 5)
        lump.heat_by(100)
        self.assertEqual(lump.state, "gas")
        self.assertEqual(self.callback_counter, 10)

    def test_transition_exceptions(self):
        """tests whether non-existent transitions are detected"""
        lump = self.object_class("lump")
        with self.assertRaises(TransitionError):
            lump.evaporate()
        with self.assertRaises(TransitionError):
            lump.cool()
        with self.assertRaises(TransitionError):
            lump.state = "gas"

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



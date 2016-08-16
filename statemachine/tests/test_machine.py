import unittest

from statemachine.machine import BaseStateObject, StateMachine, TransitionError, MachineError

__author__ = "lars van gemerden"


class StateMachineTest(unittest.TestCase):

    def setUp(self):
        self.callback_counter = 0
        self.temperature_ignore = True

        def callback(obj, old_state, new_state):
            self.assertEqual(type(obj), Matter)
            self.callback_counter += 1

        def temp_checker(min, max):
            def inner(obj, old_state, new_state):
                return min < obj.temperature <= max or self.temperature_ignore
            return inner

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

            machine = self.machine

            def __init__(self, name, temperature=0):
                super(Matter, self).__init__(initial="solid")
                self.name = name
                self.temperature = temperature

            def heat_by(self, delta):
                self.temperature += delta
                self.heat()

            def cool_by(self, delta):
                self.temperature -= delta
                self.cool()

            def __str__(self):
                return self.name + "(%s)" % self.state

        self.object_class = Matter

    def test_setup(self):
        self.assertEqual(len(self.machine.states), 3)
        self.assertEqual(len(self.machine.transitions), 4)
        self.assertEqual(len(self.machine.triggers), 8)

    def test_triggers(self):
        lump = self.object_class("lump")
        lump.melt()
        self.assertEqual(lump.state, "liquid")
        lump.evaporate()
        self.assertEqual(lump.state, "gas")
        lump.condense()
        self.assertEqual(lump.state, "liquid")
        lump.freeze()
        self.assertEqual(lump.state, "solid")

    def test_same_triggers(self):
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
        lump = self.object_class("lump")
        lump.melt()
        self.assertEqual(self.callback_counter, 5)
        lump.heat()
        self.assertEqual(self.callback_counter, 10)
        lump.cool()
        self.assertEqual(self.callback_counter, 15)

    def test_condition(self):
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
        lump = self.object_class("lump")
        with self.assertRaises(TransitionError):
            lump.evaporate()
        with self.assertRaises(TransitionError):
            lump.cool()
        with self.assertRaises(TransitionError):
            lump.state = "gas"

    def test_machine_errors(self):
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
                    {"old_state": "solid", "new_state": "liquid", "triggers": ["melt"]},
                    {"old_state": "solid", "new_state": "liquid", "triggers": ["melt"]},
                ]
            )



__author__ = "lars van gemerden"

import unittest
from collections import defaultdict

from ..exception import TransitionError, MachineError
from ..machine import state_machine
from ..stateful import StatefulObject
from ..configuration import transitions, default_case, states, state, transition, switch, case
from ..tools import Path, stopwatch


def count_transitions(state):
    return len(list(state.iter_transitions()))


class TestSimplestStateMachine(unittest.TestCase):

    def setUp(self):
        class Lamp(StatefulObject):
            state = state_machine(states=states("off", "on"))

            def __init__(self):
                super().__init__()
                self.on_count = 0
                self.off_count = 0
                self.stays = defaultdict(list)

            @state.on_entry('on')
            def inc_on_count(self, *args, **kwargs):
                self.on_count += 1

            @state.on_entry('off')
            def inc_on_count(self, *args, **kwargs):
                self.off_count += 1

            @state.on_stay('off')
            @state.on_stay('on')
            def do_on_stay(self, string="", *args, **kwargs):
                self.stays[self.state].append(string)

        self.lamp = Lamp()

    def test_setup(self):
        pass

    def test_construction(self):
        """test whether all states, transitions and trigger(s) are in place"""
        self.assertEqual(len(type(self.lamp).state), 2)
        self.assertEqual(count_transitions(type(self.lamp).state), 4)

    def test_triggers(self):
        """test the basio trigger functions and the resultig states"""
        self.assertEqual(self.lamp.state, "off")
        self.lamp.goto_on()
        self.assertEqual(self.lamp.state, "on")
        self.lamp.goto_off()
        self.assertEqual(self.lamp.state, "off")
        self.lamp \
            .goto_on("a") \
            .goto_on("b") \
            .goto_off("c") \
            .goto_off("d")
        self.assertEqual(self.lamp.state, "off")
        self.assertEqual(self.lamp.on_count, 2)
        self.assertEqual(self.lamp.off_count, 2)
        assert self.lamp.stays == dict(on=["b"], off=["d"])


class TestSimpleStateMachine(unittest.TestCase):

    def setUp(self):
        class Lamp(StatefulObject):
            state = state_machine(states=states(off=state(info="not turned on"),
                                                on=state(info="not turned off")),
                                  transitions=transitions(transition("off", "on", trigger="flick", info="turn the light on"),
                                                          transition("on", "off", trigger="flick", info="turn the light off")))

            def __init__(self):
                super().__init__()
                self.on_count = 0
                self.off_count = 0

            @state.on_entry('on')
            def inc_on_count(self, **kwargs):
                self.on_count += 1

            @state.on_entry('off')
            def inc_off_count(self, **kwargs):
                self.off_count += 1

        self.lamp = Lamp()

    def test_setup(self):
        pass

    def test_construction(self):
        """test whether all states, transitions and trigger(s) are in place"""
        self.assertEqual(len(type(self.lamp).state), 2)
        self.assertEqual(count_transitions(type(self.lamp).state), 2)

    def test_triggers(self):
        """test the basio trigger functions and the resultig states"""
        self.assertEqual(self.lamp.state, "off")
        self.lamp.flick()
        self.assertEqual(self.lamp.state, "on")
        self.lamp.flick()
        self.assertEqual(self.lamp.state, "off")
        self.lamp.flick().flick()
        self.assertEqual(self.lamp.state, "off")
        self.assertEqual(self.lamp.on_count, 2)
        self.assertEqual(self.lamp.off_count, 2)

    def test_info(self):
        self.assertEqual(type(self.lamp).state.sub_states["on"].info, "not turned off")
        self.assertEqual(type(self.lamp).state['off'].trigger_transitions['flick'][Path('on')].info, "turn the light on")


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

            @state.on_transfer('gas', 'liquid', )
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

    def test_state_names(self):
        self.assertEqual(list(self.machine),
                         ['solid', 'liquid', 'gas'])

    def test_triggers_property(self):
        self.assertEqual(self.machine.triggers,
                         {'heat', 'melt', 'cool', 'evaporate', 'freeze', 'condense'})

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
        with self.assertRaises(TransitionError):
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
            class Matter(StatefulObject):
                state = state_machine(
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
        with self.assertRaises(MachineError):
            # Note the RuntimeError, this is because the error is raised in StateMachine.__set_name__, where
            #   the condition function is looked up on the class; any error raised there is caught and
            #   reraised as a RuntimeError. There is no place to catch this error within the state machine.
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

        class B(StatefulObject):
            state = state_machine(states=states("A"))

        b = B()

        with self.assertRaises(TransitionError):
            b.state = "liquid"


class TestWildcardStateMachine(unittest.TestCase):
    """test the case where transition configuration contains wildcards '*' """

    def setUp(self):
        """called before any individual test method"""
        self.callback_counter = 0  # rest for every tests; used to count number of callbacks from machine

        # create a machine based on phase changes of matter (solid, liquid, gas)

        self.machine = state_machine(
            states=states(solid=state(),
                          liquid=state(),
                          gas=state(),
                          void=state()),

            transitions=(transition('solid', 'liquid', trigger=["melt", "heat"]),
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
                """checks whether the object arrives; callback_counter is used to check whether callbacks are all called"""
                self.assertEqual(type(obj), Matter)
                self.callback_counter += 1

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
                states=states(solid=state(),
                              liquid=state(),
                              gas=state()),
                transitions=(transition(["solid", "liquid"], 'gas', trigger='zap'),
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
        self.assertEqual(len(self.machine.sub_states), 3)
        self.assertEqual(count_transitions(self.machine), 4)

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
                                        transition('broken', switch(case('on', 'was_on'),
                                                                    default_case('off', on_transfer='fix_to_off')),
                                                   on_transfer='in_any_case',
                                                   trigger='fix')),
            )

            def __init__(self, state=None):
                super(LightSwitch, self).__init__(state=state)
                self._old_state = None
                self.fix_to_off_called = False
                self.in_any_case_called = False

            @state.on_exit('*')
            def store_state(self):
                self._old_state = self.state

            def was_on(self):
                return str(self._old_state) == "on"

            def fix_to_off(self, **kwargs):
                self.fix_to_off_called = True

            def in_any_case(self, **kwargs):
                self.in_any_case_called = True

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

    def test_double_on_transfer(self):
        light_switch = self.object_class(state="on")
        light_switch.smash()
        light_switch.fix()
        assert light_switch.fix_to_off_called == False
        assert light_switch.in_any_case_called == True

        light_switch = self.object_class(state="off")
        light_switch.smash()
        light_switch.fix()
        assert light_switch.fix_to_off_called == True
        assert light_switch.in_any_case_called == True

    def test_machine_error(self):
        class Light(StatefulObject):
            state = state_machine(
                states=states(
                    on=state(),
                    off=state(),
                    broken=state()),
                transitions=(transition('off', 'on', trigger=["turn_on", "switch"]),
                             transition('on', 'off', trigger=["turn_off", "switch"]),
                             transition(["on", "off"], 'broken', trigger="smash"),
                             transition('broken', switch(default_case('off'),  # wrong order is fixed
                                                         case('on', 'was_on')),
                                        trigger='fix'))
            )

            def was_on(self, **kwargs):
                return False


class TestSwitchedDoubleTransitionStateMachine(unittest.TestCase):
    def test(self):  # same as in old machine
        pass


class TestNestedStateMachine(unittest.TestCase):
    """test the case where transition configuration contains wildcards '*' """

    def setUp(self):
        """called before any individual test method"""
        # create a machine config based on phase changes of matter (solid, liquid, gas)
        self.machine = state_machine(
            states=states(off=state(states(working=state(),
                                           broken=state()),
                                    transitions(transition('working', 'broken', trigger='smash'),
                                                transition('broken', 'working', trigger='fix'))),

                          on=state(states(waiting=state(),
                                          washing=state(),
                                          drying=state()),
                                   transitions(transition('waiting', 'washing', trigger='wash'),
                                               transition('washing', 'drying', trigger='dry'),
                                               transition('drying', 'waiting', trigger='stop')))),
            transitions=(transition('off.working', 'on', trigger=["turn_on", "flick"]),
                         transition('on', 'off', trigger=["turn_off", "flick"]),
                         transition(('on.*', 'off'), 'off.broken', trigger=["smash"]),
                         transition('off.working', 'on.drying', trigger=["just_dry_already"]))
        )

        class WashingMachine(StatefulObject):
            state = self.machine

            def __init__(self):
                super().__init__()
                self.exit_counter = 0  # reset for every tests; used to count number of callbacks from machine
                self.entry_counter = 0  # reset for every tests; used to count number of callbacks from machine
                self.any_counter = 0  # reset for every tests; used to count number of callbacks from machine
                self.transfer_counter = 0
                self.before_exits = {}
                self.after_entries = {}

            @state.on_exit('off.*', 'on.*')
            def inc_exit_counter(self, **kwargs):
                """basic check + counts the number of times the object exits a state"""
                self.exit_counter += 1

            @state.on_entry('off.*', 'on.*')
            def inc_entry_counter(self, **kwargs):
                """basic check + counts the number of times the object enters a state"""
                self.entry_counter += 1

            @state.on_exit('*')
            def inc_any_counter(self, **kwargs):
                """ will be used to check whether this method will be looked up in super states """
                self.any_counter += 1

            @state.on_transfer('off', 'on')
            def inc_transfer_counter(self, **kwargs):
                self.transfer_counter += 1

            @state.before_exit()
            def append_to_before_root(self, **kwargs):
                self.before_exits['root'] = self.state

            @state.after_entry()
            def append_to_after_root(self, **kwargs):
                self.after_entries['root'] = self.state

            @state.before_exit('off')
            def append_to_before_off(self, **kwargs):
                self.before_exits['off'] = self.state

            @state.after_entry('off')
            def append_to_after_off(self, **kwargs):
                self.after_entries['off'] = self.state

        self.object_class = WashingMachine

    def assert_counters(self, washer, exit_counter, entry_counter, before_counter, transfer_counter):
        self.assertEqual(washer.exit_counter, exit_counter)
        self.assertEqual(washer.entry_counter, entry_counter)
        self.assertEqual(washer.any_counter, before_counter)
        self.assertEqual(washer.transfer_counter, transfer_counter)

    def test_construction(self):
        """test whether all states, transitions and trigger(s) are in place"""
        self.assertEqual(len(self.object_class.state), 2)
        self.assertEqual(count_transitions(self.machine), 18)
        assert self.object_class.state.default_path == Path("off.working")
        child_state = self.object_class.state["on"]
        self.assertEqual(len(child_state), 3)
        self.assertEqual(count_transitions(child_state), 12)
        assert child_state.default_path == Path("waiting")
        child_state = self.object_class.state["off"]
        self.assertEqual(len(child_state), 2)
        self.assertEqual(count_transitions(child_state), 6)
        assert child_state.default_path == Path("working")
        assert child_state.root == self.object_class.state

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

    def test_decoration_double_wildcard(self):
        machine = self.object_class.state

        exits = []
        entries = []

        def exit_callback(obj):
            exits.append(obj.state)

        def entry_callback(obj):
            entries.append(obj.state)

        machine.on_exit('*.*')(exit_callback)
        machine.on_entry('*.*')(entry_callback)
        washer = self.object_class()
        washer.turn_on()

        assert exits == ['off.working']
        assert entries == ['on.waiting']

    def test_before_after(self):
        washer = self.object_class()

        def assert_before_after(before, after):
            def assert_before(key):
                assert washer.before_exits.get(key) == before[key]

            def assert_after(key):
                assert washer.after_entries.get(key) == after[key]

            assert_before('root')
            assert_before('off')
            assert_after('root')
            assert_after('off')

        assert washer.state == 'off.working'
        assert_before_after(before=dict(root=None, off=None),
                            after=dict(root=None, off=None))
        washer.smash()
        assert washer.state == 'off.broken'
        assert_before_after(before=dict(root='off.working', off='off.working'),
                            after=dict(root='off.broken', off='off.broken'))
        washer.fix()
        assert washer.state == 'off.working'
        assert_before_after(before=dict(root='off.broken', off='off.broken'),
                            after=dict(root='off.working', off='off.working'))
        washer.turn_on()
        assert washer.state == 'on.waiting'
        assert_before_after(before=dict(root='off.working', off='off.working'),
                            after=dict(root='on.waiting', off='off.working'))
        washer.smash()
        assert washer.state == 'off.broken'
        assert_before_after(before=dict(root='on.waiting', off='off.working'),
                            after=dict(root='off.broken', off='off.broken'))

    def test_on_stay(self):
        machine = self.object_class.state

        inner_stays = []
        outer_stays = []

        def inner_callback(obj):
            inner_stays.append(obj.state)

        def outer_callback(obj):
            outer_stays.append(obj.state)

        machine.on_stay('off')(outer_callback)
        machine.on_stay('off.broken')(inner_callback)
        washer = self.object_class()
        assert washer.state == 'off.working'
        washer.smash()
        assert washer.state == 'off.broken'

        assert inner_stays == []  # inner_callback not been called
        assert outer_stays == ['off.broken']

        washer.smash()
        assert washer.state == 'off.broken'

        assert inner_stays == ['off.broken']  # inner_callback has been called
        assert outer_stays == ['off.broken', 'off.broken']

    def test_triggering(self):
        washer = self.object_class()
        self.assertEqual(washer.state, "off.working")
        self.assert_counters(washer, 0, 0, 0, 0)

        washer.flick()
        self.assertEqual(washer.state, "on.waiting")
        self.assert_counters(washer, 1, 1, 1, 1)

        washer.wash()
        self.assertEqual(washer.state, "on.washing")
        self.assert_counters(washer, 2, 2, 1, 1)

        washer.dry()
        self.assertEqual(washer.state, "on.drying")
        self.assert_counters(washer, 3, 3, 1, 1)

        washer.flick()
        self.assertEqual(washer.state, "off.working")
        self.assert_counters(washer, 4, 4, 2, 1)

        washer.just_dry_already()
        self.assertEqual(washer.state, "on.drying")
        self.assert_counters(washer, 5, 5, 3, 2)

    def test_state_string(self):
        assert str(self.object_class.state["on"]) == "State('on')"
        assert str(self.object_class.state["on"]["washing"]) == "State('on.washing')"

    def test_transition_errors(self):
        washer = self.object_class()
        self.assert_counters(washer, 0, 0, 0, 0)
        self.assertEqual(washer.state, "off.working")

        with self.assertRaises(TransitionError):
            washer.dry()
        self.assertEqual(washer.state, "off.working")
        self.assert_counters(washer, 0, 0, 0, 0)

        with self.assertRaises(TransitionError):
            washer.fix()
        self.assertEqual(washer.state, "off.working")
        self.assert_counters(washer, 0, 0, 0, 0)

        washer.smash()
        self.assertEqual(washer.state, "off.broken")
        self.assert_counters(washer, 1, 1, 0, 0)

    def test_as_json_dict_and_repr(self):
        json_dict = self.object_class.state.as_json_dict()
        assert 'states' in json_dict
        assert 'transitions' in json_dict['states']['off']['states']['working']
        assert set(json_dict['states']) == {'on', 'off'}
        assert 'states' in json_dict['states']['on']

        json_string = repr(self.object_class.state)
        assert len(json_string)


class TestCallbackDecorators(unittest.TestCase):
    """test the case where transition configuration contains wildcards '*' """

    def setUp(self):
        """called before any individual test method"""
        # create a machine config based on phase changes of matter (solid, liquid, gas)
        self.machine = state_machine(
            states=states(off=state(states(working=state(),
                                           broken=state()),
                                    transitions(transition('working', 'broken', trigger='smash'),
                                                transition('broken', 'working', trigger='fix'))),
                          on=state(states(waiting=state(),
                                          washing=state(),
                                          drying=state()),
                                   transitions(transition('waiting', 'washing', trigger='wash'),
                                               transition('washing', 'drying', trigger='dry'),
                                               transition('drying', 'waiting', trigger='stop')))),
            transitions=(transition('off.working', 'on', trigger="turn_on"),
                         transition('on', 'off', trigger="turn_off"),
                         transition(('on', 'off'), 'off.broken', trigger="smash"),
                         transition('off.broken', 'off.working', trigger="fix"))
        )

        class WashingMachine(StatefulObject):
            state = self.machine

            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.fix_attempts = 0
                self.stay_counters = defaultdict(int)
                self.exit_counters = defaultdict(int)
                self.entry_counters = defaultdict(int)
                self.trans_counters = defaultdict(int)

            @property
            def path(self):
                return Path(self.state)

            @state.condition('off.broken', 'off.working')
            def second_try(self, **kwargs):
                self.fix_attempts += 1
                if self.fix_attempts >= 2:
                    self.fix_attempts = 0
                    return True
                return False

            @state.on_stay('off.broken')
            def not_fixed(self, **kwargs):
                self.stay_counters[self.state] += 1

            @state.on_exit('off.*', 'on.*')
            def on_exit(self, **kwargs):
                """basic check + counts the number of times the object exits a state"""
                self.exit_counters[self.state] += 1

            @state.on_entry('off.*', 'on.*')
            def on_entry(self, **kwargs):
                """basic check + counts the number of times the object enters a state"""
                self.entry_counters[self.state] += 1

            @state.on_transfer('off', 'on')
            @state.on_transfer('on', 'off')
            def on_transfer(self, **kwargs):
                self.trans_counters[self.state] += 1

        self.object_class = WashingMachine

    def test_cycle(self):
        washer = self.object_class()
        assert washer.state == "off.working"
        washer.turn_on()
        assert washer.exit_counters["off.working"] == 1
        assert washer.entry_counters["on.waiting"] == 1
        assert washer.trans_counters["on.waiting"] == 1
        washer.wash()
        assert washer.exit_counters["on.waiting"] == 1
        assert washer.entry_counters["on.washing"] == 1
        assert washer.trans_counters["on.washing"] == 0
        washer.dry()
        assert washer.exit_counters["on.washing"] == 1
        assert washer.entry_counters["on.drying"] == 1
        assert washer.trans_counters["on.drying"] == 0
        washer.stop()
        assert washer.exit_counters["on.drying"] == 1
        assert washer.entry_counters["on.waiting"] == 2
        assert washer.trans_counters["on.waiting"] == 1
        washer.turn_off()
        assert washer.exit_counters["on.waiting"] == 2
        assert washer.entry_counters["off.working"] == 1
        assert washer.trans_counters["off.working"] == 1

    def test_condition_and_on_stay(self):
        washer = self.object_class(state="on.waiting")
        assert washer.state == "on.waiting"
        washer.smash()
        assert washer.exit_counters["on.waiting"] == 1
        assert washer.entry_counters["off.broken"] == 1
        assert washer.stay_counters["off.broken"] == 0
        assert washer.state == "off.broken"
        washer.fix()
        assert washer.exit_counters["off.broken"] == 0
        assert washer.entry_counters["off.broken"] == 1
        assert washer.stay_counters["off.broken"] == 1
        assert washer.state == "off.broken"
        washer.fix()
        assert washer.exit_counters["off.broken"] == 1
        assert washer.entry_counters["off.working"] == 1
        assert washer.stay_counters["off.broken"] == 1
        assert washer.state == "off.working"

    def test_as_json_dict(self):
        json_dict = self.object_class.state.as_json_dict()
        assert any(t.get('condition') for t in json_dict['states']['off']['states']['broken']['transitions'])


class TestPerformance(unittest.TestCase):

    def setUp(self):
        class Lamp(StatefulObject):
            state = state_machine(states=states(off=state(),
                                                on=state()),
                                  transitions=(transition("off", "on", trigger="flick"),
                                               transition("on", "off", trigger="flick")))

            @state.on_entry('on')
            def inc_on_count(self):
                pass

            @state.on_entry('off')
            def inc_on_count(self):
                pass

        self.lamp = Lamp()

    def test_performance(self):
        lamp = self.lamp

        N = 100_000
        with stopwatch() as stop_time:
            for _ in range(N):
                lamp.flick()
        assert stop_time() / N < 2.0e-6  # < 1.0e-6 (windows, i7, 2016), but unit-testing by github Actions can be slower
        print('\n', stop_time() / N)


class TestMultiState(unittest.TestCase):

    def setUp(self):
        class MoodyColor(StatefulObject):
            color = state_machine(
                states=states(
                    red=state(),
                    blue=state(),
                    green=state(),
                ),
                transitions=[
                    transition('red', 'blue', trigger=['next', 'change']),
                    transition('blue', 'green', trigger=['next', 'change']),
                    transition('green', 'red', trigger=['next', 'change']),
                ],
            )

            mood = state_machine(
                states=dict(
                    good=state(),
                    bad=state(),
                    ugly=state(),
                ),
                transitions=[
                    transition('good', 'bad', trigger='next'),
                    transition('bad', 'ugly', trigger='next'),
                    transition('ugly', 'good', trigger='next'),
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

            @mood.on_entry('*')
            @color.on_entry('*')
            def count_calls(self):
                self.counter += 1

            @mood.on_exit('*')
            @color.on_exit('*')
            def on_exit(self):
                self.exit_history.append(self.state())

            @mood.on_entry('*')
            @color.on_entry('*')
            def on_entry(self):
                self.entry_history.append(self.state())

            @mood.on_transfer('*', '*')
            @color.on_transfer('*', '*')
            def on_transfer(self):
                self.transfer_history.append(self.state())

        self.state_class = MoodyColor

    def test_init_sub_state(self):
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
        moodycolor.trigger_initial()
        assert moodycolor.entry_history == [{'color': 'red', 'mood': 'good'},
                                            {'color': 'red', 'mood': 'good'}]
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


class TestContextManager(unittest.TestCase):

    def setUp(self):
        """called before any individual test method"""

        # create a machine based on phase changes of matter (solid, liquid, gas)

        class Radio(StatefulObject):
            """object class fo which the state is managed"""
            state = state_machine(
                states=states('off', 'on'),
                transitions=[
                    transition("off", "on", trigger="flick"),
                    transition("on", "off", trigger="flick"),
                ],
            )

            def __init__(self):
                super().__init__()
                self.managed = False

            @state.on_entry('on', 'off')
            def on_action(self, context, **kwargs):
                assert context == 'ctx'
                assert self.managed

            @state.contextmanager
            def object_manager(self, **kwargs):
                self.managed = True
                yield 'ctx'
                self.managed = False

        self.object_class = Radio

    def test_manager(self):
        radio = self.object_class()
        assert radio.managed == False
        radio.flick()
        assert radio.managed == False
        radio.flick()
        assert radio.managed == False


class TestCallbackArguments(unittest.TestCase):

    def setUp(self):
        class Radio(StatefulObject):
            """object class fo which the state is managed"""
            state = state_machine(
                states=states('off', 'on'),
                transitions=[
                    transition("off", "on", trigger="flick"),
                ],
            )

            def __init__(self, testcase):
                super(Radio, self).__init__()
                self.testcase = testcase

            @state.condition('off', 'on')
            def condition(self, a, **kwargs):
                assert a == 1
                return True

            @state.on_entry('on')
            def on_entry(self, b, **kwargs):
                assert b == 2

            @state.on_exit('off')
            def on_exit(self, c, **kwargs):
                assert c == 3

            @state.on_transfer('off', 'on')
            def on_transfer(self, d, **kwargs):
                assert d == 4

            @state.on_exit('*')
            def on_any_exit(self, e, **kwargs):
                assert e == 5

            @state.on_entry('*')
            def on_any_entry(self, f, **kwargs):
                assert f == 6

        self.object_class = Radio

    def test_callbacks(self):
        radio = self.object_class(self)
        radio.flick(a=1, b=2, c=3, d=4, e=5, f=6, ignored=7)


class TestPrepare(unittest.TestCase):

    def setUp(self):
        """called before any individual test method"""

        class LightSwitch(StatefulObject):
            state = state_machine(
                states=states('on', 'off'),
                transitions=[
                    transition('off', 'on', trigger="flick"),
                    transition('on', 'off', trigger="flick"),
                ],
            )

            def __init__(self, time=0, *args, **kwargs):
                super(LightSwitch, self).__init__(*args, **kwargs)
                self.time = time

            @state.prepare
            def prepare(self, hours, *args, **kwargs):
                self.time = (self.time + hours) % 24  # increment time with hours and start from 0 if >24 (midnight)

            @state.condition('off', 'on')
            def is_night(self, *args, **kwargs):
                return self.time < 6 or self.time > 18

        self.lightswitch_class = LightSwitch

    def test_override(self):
        lightswitch = self.lightswitch_class(time=0,
                                             state="on")
        self.assertTrue(lightswitch.is_night())
        lightswitch.flick(hours=7)
        assert lightswitch.time == 7
        self.assertTrue(lightswitch.state == "off")
        lightswitch.flick(hours=7)
        assert lightswitch.time == 14
        self.assertTrue(lightswitch.state == "off")
        lightswitch.flick(hours=7)
        assert lightswitch.time == 21
        lightswitch.flick(hours=7)  # lightswitch.time == 28 % 24 == 4
        assert lightswitch.time == 4
        assert lightswitch.state == "off"


class TestMultiStateMachine(unittest.TestCase):
    def setUp(self):
        class MultiSome(StatefulObject):
            color = state_machine(
                states=states("red", "blue", "green"),
                transitions=[
                    transition('red', 'blue', trigger='next'),
                    transition('blue', 'green', trigger='next'),
                    transition('green', 'red', trigger='next'),
                ],
            )
            mood = state_machine(
                states=states("good", "bad", "ugly"),
                transitions=[
                    transition('good', 'bad', trigger='next'),
                    transition('bad', 'ugly', trigger='next'),
                    transition('ugly', 'good', trigger='next'),
                ],
            )

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.history = dict(color=[], mood=[])

            @color.on_exit('*')
            def color_callback(self):
                self.history['color'].append(self.color)

            @mood.on_exit('*')
            def mood_callback(self):
                self.history['mood'].append(self.mood)

        self.obj_class = MultiSome

    def test_transitions(self):
        some = self.obj_class()
        for _ in range(6):
            some.next()

        assert some.history['color'] == ['red', 'blue', 'green', 'red', 'blue', 'green']
        assert some.history['mood'] == ['good', 'bad', 'ugly', 'good', 'bad', 'ugly']


class TestMultiStateMachineOldCallbacks(unittest.TestCase):
    def setUp(self):
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

        self.obj_class = MultiSome

    def test_transitions(self):
        some = self.obj_class()
        for _ in range(6):
            some.next()

        assert some.history['color'] == ['red', 'blue', 'green', 'red', 'blue', 'green']
        assert some.history['mood'] == ['good', 'bad', 'ugly', 'good', 'bad', 'ugly']


class TestReadmeOne(unittest.TestCase):

    def setUp(self):
        class User(StatefulObject):
            state = state_machine(
                states=states(new=state(),  # default: exactly the same result as using just the state name
                              blocked=state(),
                              active=state(states=states('logged_out', 'logged_in'),
                                           transitions=[
                                               transition('logged_out', 'logged_in', trigger='log_in'),
                                               transition('logged_out', 'logged_out', trigger='log_in'),
                                               transition('logged_in', 'logged_out', trigger='log_out')
                                           ])
                              ),
                transitions=[
                    transition('new', 'active', trigger='activate'),
                    transition('active', 'blocked', trigger='block'),
                    transition('blocked', 'active', trigger='unblock'),
                ]
            )

            def __init__(self, username):
                super().__init__(state='new')
                self.username = username
                self.password = None

            @state.on_entry('active')
            def set_password(self, password):
                self.password = password

            @state.condition('active.logged_out',
                             'active.logged_in')
            def verify_password(self, password):
                return self.password == password

            @state.on_entry('active.logged_in')
            def print_welcome(self, **ignored):
                print(f"Welcome back {self.username}")

            @state.on_transfer('active.logged_out',
                               'active.logged_out')  # this transition is auto_generated by setting a condition
            def print_welcome(self, **ignored):
                print(f"Sorry, {self.username}, you gave an incorrect password")

        self.user_class = User

    def test(self):
        user = self.user_class('rosemary').activate(password='very_secret').log_in(password='very_secret')
        assert user.state == 'active.logged_in'

        user = self.user_class('rosemary').activate(password='very_secret').log_in(password='not_very_secret')
        assert user.state == 'active.logged_out'


class TestReadmeTwo(unittest.TestCase):

    def setUp(self):
        class User(StatefulObject):
            state = state_machine(
                states=states(
                    new=state(),  # default: exactly the same result as using just the state name
                    blocked=state(),
                    active=state(
                        states=states('logged_out', 'logged_in'),
                        transitions=[
                            transition('logged_out', 'logged_in', trigger='login'),
                            transition('logged_out', 'logged_out', trigger='login'),
                            transition('logged_in', 'logged_out', trigger='logout'),
                        ]
                    ),
                    deleted=state(),
                ),
                transitions=[
                    transition('new', 'active', trigger='activate'),
                    transition('active', 'blocked', trigger='block'),
                    transition('active.logged_out', 'blocked', trigger='login'),
                    transition('blocked', 'active', trigger='unblock'),
                    transition('*', 'deleted', trigger='delete'),
                ]
            )

            def __init__(self, username, max_logins=5):
                super().__init__(state='new')
                self.username = username
                self.password = None
                self.max_logins = max_logins
                self.login_count = 0

            @state.on_entry('active')
            def set_password(self, password):
                self.password = password

            @state.condition('active.logged_out',
                             'active.logged_in')
            def verify_password(self, password):
                return self.password == password

            @state.condition('active.logged_out',
                             'blocked',
                             trigger='login')
            def check_login_count(self, **ignored):
                return self.login_count >= self.max_logins

            @state.on_transfer('active.logged_out',
                               'active.logged_out')  # this transition was auto-generated by setting a condition on logged_out to logged_in
            def inc_login_count(self, **ignored):
                self.login_count += 1

            @state.on_exit('blocked')
            @state.on_entry('active.logged_in')
            def reset_login_count(self, **ignored):
                self.login_count = 0

        self.user_class = User

    def test(self):
        user = self.user_class('rosemary').activate(password='very_secret')

        for _ in range(user.max_logins):
            user.login(password='very_wrong')
            assert user.state == 'active.logged_out'

        user.login(password='also_wrong')  # the 6th time
        assert user.state == 'blocked'


class TestCaching(unittest.TestCase):
    """test the case where transition configuration contains wildcards '*' """

    def setUp(self):
        class User(StatefulObject):
            state = state_machine(
                states=states(
                    new=state(),  # default: exactly the same result as using just the state name
                    active=state(
                        states=states('logged_out', 'logged_in'),
                        transitions=[
                            transition('logged_out', 'logged_in', trigger='login'),
                            transition('logged_in', 'logged_out', trigger='logout')
                        ]
                    ),
                ),
                transitions=[
                    transition('new', 'active', trigger='activate'),
                ]
            )

            def __init__(self, username):
                super().__init__(state='new')
                self.username = username
                self.password = None

            @state.on_entry('active')
            def set_password(self, password):
                self.password = password

        self.user_class = User

    def test_late_callback(self):
        user = self.user_class(username='bob')
        test_value = [False]

        @self.user_class.state.on_entry('active')
        def func(obj, *args, **kwargs):
            test_value[0] = True

        user.activate("pwd")
        assert test_value[0] == True

    def test_no_late_condition(self):
        user = self.user_class(username='bob')
        with self.assertRaises(MachineError):
            @self.user_class.state.condition('active.logged_out',
                                             'active.logged_in')
            def func():
                pass


class TestConditionWithDoubleOldState(unittest.TestCase):
    """test the case where transition configuration contains wildcards '*' """

    def setUp(self):
        class User(StatefulObject):
            state = state_machine(
                states=states(
                    new=state(),  # default: exactly the same result as using just the state name
                    active=state(
                        states=states('logged_out', 'logged_in'),
                        transitions=[
                            transition(('logged_out', 'logged_in'), 'logged_in', trigger='login'),
                            transition('logged_in', 'logged_out', trigger=('login', 'logout'))
                        ]
                    ),
                ),
                transitions=[
                    transition('new', 'active', trigger='activate'),
                ]
            )

            def __init__(self, username):
                super().__init__(state='new')
                self.username = username
                self.password = None

            @state.on_entry('active')
            def set_password(self, password):
                self.password = password

            @state.condition(('active.logged_out',
                              'active.logged_in'),
                             'active.logged_in')
            def verify_password(self, password):
                return password == self.password

        self.user_class = User

    def test_transitions(self):
        user = self.user_class(username='bob').activate('password')

        user.login("wrong")
        assert user.state == 'active.logged_out'
        user.login("password")
        assert user.state == 'active.logged_in'
        user.login("password")
        assert user.state == 'active.logged_in'
        user.login("wrong")
        assert user.state == 'active.logged_out'


class TestNameArgument(unittest.TestCase):
    """test the case where transition configuration contains wildcards '*' """

    def setUp(self):
        class User(StatefulObject):
            machine = state_machine(
                name='state',
                states=states(
                    new=state(),  # default: exactly the same result as using just the state name
                    active=state(),
                ),
                transitions=[
                    transition('new', 'active', trigger='activate'),
                ]
            )

            def __init__(self, username):
                super().__init__(state='new')
                self.username = username
                self.password = None

            @machine.on_entry('active')
            def set_password(self, password):
                self.password = password

        self.user_class = User

    def test_name_argument(self):
        user = self.user_class(username='bob')
        assert user.state == 'new'
        assert user.machine == 'new'
        user.activate('password')
        assert user.state == 'active'
        assert user.machine == 'active'
        assert 'state' in user.__dict__
        assert 'machine' not in user.__dict__
        assert hasattr(user, 'state')
        assert hasattr(user, 'machine')

from functools import partial


def listify(list_or_item):
    try:
        return list(list_or_item)
    except TypeError:
        return [list_or_item]


class MachineError(ValueError):
    pass


class TransitionError(ValueError):
    pass


class State(object):

    def __init__(self, machine, name, on_entry=(), on_exit=()):
        self.machine = machine
        self.name = name
        self._on_entry = listify(on_entry)
        self._on_exit = listify(on_exit)

    def on_entry(self, obj):
        for callback in self._on_entry:
            callback(obj, state=self.name)

    def on_exit(self, obj):
        for callback in self._on_exit:
            callback(obj, state=self.name)


class Transition(object):

    def __init__(self, machine, old_state, new_state, on_transfer=(), condition=lambda obj: True):
        self.machine = machine
        self.old_state = old_state
        self.new_state = new_state
        self._on_transfer = listify(on_transfer)
        self.condition = condition

    def on_transfer(self, obj):
        for callback in self._on_transfer:
            callback(obj, old_state=self.old_state.name, new_state=self.new_state.name)

    def execute(self, obj):
        if self.condition(obj):
            self.machine.before_any_exit(obj)
            self.old_state.on_exit(obj)
            self.on_transfer(obj)
            obj.change_state(self.new_state.name)
            self.new_state.on_entry(obj)
            self.machine.after_any_entry(obj)

    def __str__(self):
        return "<%s, %s>" %(self.old_state.name, self.new_state.name)


class StateMachine(object):

    state_class = State
    transition_class = Transition

    def __init__(self, name, states, transitions, before_any_exit=(), after_any_entry=()):
        self.name = name
        self.states = self._create_states(states)
        self.transitions = self._create_transitions(transitions)
        self.triggers = self._create_trigger_dict(transitions)
        self._before_any_exit = listify(before_any_exit)
        self._after_any_entry = listify(after_any_entry)

    def _create_states(self, states):
        state_dict = {}
        for state in states:
            if state["name"] in state_dict:
                raise MachineError("two states with the same name in state machine")
            state_dict[state["name"]] = self.state_class(machine=self, **state)
        return state_dict

    def _create_transitions(self, transitions):
        transition_dict = {}
        for trans in transitions:
            if (trans["old_state"], trans["new_state"]) in transition_dict:
                raise MachineError("two transitions between same states in state machine")
            transition = self.transition_class(machine=self,
                                               old_state=self.states[trans["old_state"]],
                                               new_state=self.states[trans["new_state"]],
                                               on_transfer=trans.get("on_transfer", ()),
                                               condition=trans.get("condition", lambda obj: True))
            transition_dict[(trans["old_state"], trans["new_state"])] = transition
        return transition_dict

    def _create_trigger_dict(self, transitions):
        trigger_dict = {}
        for trans in transitions:
            for trigger_name in trans.get("triggers", ()):
                key = (trans["old_state"], trigger_name)
                if key in trigger_dict:
                    raise MachineError("same trigger for same start state and different transitions")
                trigger_dict[key] = self.transitions[(trans["old_state"], trans["new_state"])]
        return trigger_dict

    def before_any_exit(self, obj):
        for callback in self._before_any_exit:
            callback(obj)

    def after_any_entry(self, obj):
        for callback in self._after_any_entry:
            callback(obj)

    def do_trigger(self, trigger, obj):
        try:
            self.triggers[(obj.state, trigger)].execute(obj)
        except KeyError:
            raise TransitionError("trigger '%s' does not exist for state '%s'" % (trigger, obj.state))

    def set_state(self, state, obj):
        try:
            self.transitions[(obj.state, state)].execute(obj)
        except KeyError:
            raise TransitionError("transition <%s, %s> does not exist" % (obj.state, state))


class BaseStateObject(object):

    def __init__(self, initial="new", *args, **kwargs):
        super(BaseStateObject, self).__init__(*args, **kwargs)
        self._new_state = initial
        self._old_state = None

    def __getattr__(self, trigger):
        return partial(self.machine.do_trigger, trigger=trigger, obj=self)

    def change_state(self, state):  # override if old_state is stored e.g. in a state history
        self._old_state = self._new_state
        self._new_state = state

    def get_state(self):
        return self._new_state

    def set_state(self, state):
        if state == self._new_state:
            return
        self.machine.set_state(state, self)

    state = property(get_state, set_state)


if __name__ == "__main__":

    def printline(obj):
        print "---"

    def printer(obj, **kwargs):
        print "called 'printer' for '%s' with %s" % (str(obj), kwargs)

    class Matter(BaseStateObject):

        machine = StateMachine(
            name="matter machine",
            states=[
                {"name": "solid", "on_entry":[printer], "on_exit":[printer]},
                {"name": "liquid", "on_entry": [printer], "on_exit": [printer]},
                {"name": "gas", "on_entry": [printer], "on_exit": [printer]}
            ],
            transitions=[
                {"old_state": "solid", "new_state": "liquid", "triggers": ["melt", "heat"], "on_transfer": [printer]},
                {"old_state": "liquid", "new_state": "gas", "triggers": ["evaporate", "heat"], "on_transfer": [printer]},
                {"old_state": "gas", "new_state": "liquid", "triggers": ["condense", "cool"], "on_transfer": [printer]},
                {"old_state": "liquid", "new_state": "solid", "triggers": ["freeze", "cool"], "on_transfer": [printer]}
            ],
            after_any_entry=printline
        )

        def __init__(self, name):
            super(Matter, self).__init__(initial="solid")
            self.name = name

        def __str__(self):
            return self.name + "(%s)" % self.state

    lumpy = Matter("lumpy")

    lumpy.melt()
    lumpy.evaporate()
    lumpy.condense()
    lumpy.freeze()
    try:
        lumpy.evaporate()
    except TransitionError as e:
        print ">>> JEEP: error intercepted: " + e.message

    lumpy.heat()
    lumpy.heat()
    lumpy.cool()
    lumpy.cool()
    try:
        lumpy.cool()
    except TransitionError as e:
        print ">>> JEEP: error intercepted: " + e.message

    lumpy.state = "liquid"
    lumpy.state = "gas"
    lumpy.state = "liquid"
    lumpy.state = "solid"
    try:
        lumpy.state = "gas"
    except TransitionError as e:
        print ">>> JEEP: error intercepted: " + e.message



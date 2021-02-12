from typing import Mapping

from .exception import MachineError

"""
These are functions to make the state machine config more readable and to to validate it
"""


def states(*state_names, **state_configs):
    """ returns a dictionary with state names as keys and state configs as values """
    if not all(isinstance(s, str) for s in state_names):
        raise MachineError(f"all state names in 'states' should be of type 'str'")
    if not all(isinstance(s, dict) for s in state_configs.values()):
        raise MachineError(f"all states in 'states' should be of type 'dict'")
    all_state_configs = {s: state() for s in state_names}  # generate state configs
    all_state_configs.update(state_configs)
    return all_state_configs


def state(states=None, transitions=(), on_entry=(), on_exit=(), on_stay=(), info=""):
    if states:
        return dict(states=states or {}, transitions=transitions,
                    on_entry=on_entry, on_exit=on_exit, info=info)
    else:
        if transitions:
            raise MachineError(f"only states with sub-states can have transitions")
        return dict(on_entry=on_entry, on_exit=on_exit, on_stay=on_stay, info=info)


def transitions(*transitions_):
    if not all(isinstance(t, dict) for t in transitions_):
        raise MachineError(f"all transitions in 'transitions' should be of type 'dict'")
    return list(transitions_)


def transition(old_state, new_state, trigger, on_transfer=None, condition=None, info=""):
    if isinstance(new_state, Mapping) and case:
        raise MachineError(f"transitions with multiple (switched) end-states cannot have a single condition")
    return dict(old_state=old_state, new_state=new_state, trigger=trigger,
                on_transfer=on_transfer or [], condition=condition or [], info=info)


def switch(*state_conditions):
    if not all(isinstance(c, dict) for c in state_conditions):
        raise MachineError(f"all values in 'switch' must be 'dict'")
    return list(state_conditions)


def case(state, condition, on_transfer=None, info=""):
    return dict(state=state, condition=condition, on_transfer=on_transfer or [], info=info)


def default_case(state, on_transfer=None, info=""):
    return dict(state=state, condition=(), on_transfer=on_transfer or [], info=info)

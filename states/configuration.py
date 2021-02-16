from typing import Mapping, Callable

from .exception import MachineError

"""
Functions to validate and make the state machine config more readable.
"""


def states(*state_names, **state_configs):
    """ returns a dictionary with state names as keys and state configs as values """
    if not all(isinstance(s, str) for s in state_names):
        raise MachineError(f"all state names in 'states' should be of type 'str'")
    if not all(isinstance(s, dict) for s in state_configs.values()):
        raise MachineError(f"all states in 'states' should be of type 'dict'")
    all_state_configs = {s: state() for s in state_names}  # generate state configs
    all_state_configs.update(state_configs)
    if not len(all_state_configs):
        raise MachineError(f"no states defined in state machine configuration")
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

    result = dict(old_state=old_state, new_state=new_state, trigger=trigger,
                  on_transfer=on_transfer or [], condition=condition or [], info=info)
    return validate_dict(result, 'old_state', 'new_state', 'trigger', type_=(dict, str))


def switch(*state_conditions):
    if not all(isinstance(c, dict) for c in state_conditions):
        raise MachineError(f"all values in 'switch' must be 'dict'")
    return list(state_conditions)


def case(state, condition, on_transfer=None, info=""):
    result = dict(state=state, condition=condition, on_transfer=on_transfer or [], info=info)
    return validate_dict(validate_dict(result, 'state'), 'condition', type_=(str, Callable))


def default_case(state, on_transfer=None, info=""):
    result = dict(state=state, condition=(), on_transfer=on_transfer or [], info=info)
    return validate_dict(result, 'state')

def validate_dict(dct, *keys, type_=str):
    def check_type(key, value):
        if not isinstance(value, type_):
            raise MachineError(f"incorrect type {type_.__name__} for argument {key} in state machine configuration")

    def check_value(key, value):
        if not value:
            raise MachineError(f"missing argument {key} in state machine configuration")

    def clean_value(value):
        if isinstance(value, str):
            value = value.strip()
        return value

    def validate(key, value):
        check_type(key, value)
        value = clean_value(value)
        check_value(key, value)
        return value

    for k in keys:
        if isinstance(dct[k], (tuple, list)):
            dct[k] = list(dct[k])
            for i, value in enumerate(dct[k]):
                dct[k][i] = validate(k, value)
        else:
            dct[k] = validate(k, dct[k])
    return dct



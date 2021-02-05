from typing import Mapping, Set
from collections import deque, defaultdict

from .tools import listify, Path, MachineError, transition, copy_struct


def validate_new_state(state_name_s):
    if '*' in state_name_s or isinstance(state_name_s, (list, tuple, Set)):
        raise MachineError(f"cannot use '*' in state name '{state_name_s}' switch, "
                           f"transitions can only have a single end-state")
    return state_name_s


def get_expanded_paths(*state_names, getter, extend=False):
    """
       turns '.' separated state names in Paths and expands '*' wildcards

       :param before: if true, 'on_entry' with wildcard '*' will be put first
    """
    state_paths = [Path(state_name.replace(' ', '')) for state_name in state_names]

    expanded, queue = [], deque(state_paths)
    while len(queue):
        path = queue.popleft()  # pick the next
        head, _, tail = path.partition('*')  # split around '*' starting left
        if head == path:  # no more '*' in path
            if not extend:
                expanded.append(path)
            else:
                extend_queue = deque([path])
                while len(extend_queue):
                    head_path = extend_queue.popleft()
                    tail_paths = getter(head_path)
                    if len(tail_paths):
                        for tail_path in tail_paths:
                            extend_queue.append(head_path + tail_path)
                    else:
                        expanded.append(head_path)
        else:  # essentially replace '*' with all substates of the state pointed to by head
            for sub_state_name in getter(head):
                queue.append(head + sub_state_name + tail)
    return expanded


def get_expanded_state_names(*state_names, state_getter, extend=False):
    """ '.' separated names version of get_expanded_paths (turns paths into strings) """
    return [str(e) for e in get_expanded_paths(*state_names, getter=state_getter, extend=extend)]


def get_spliced_path(old_path, new_path):
    common_path, old_tail_path, new_tail_path = Path.splice(old_path, new_path)
    if not (len(old_tail_path) and len(new_tail_path)):
        old_tail_path = Path(common_path[-1]) + old_tail_path
        new_tail_path = Path(common_path[-1]) + new_tail_path
        common_path = common_path[:-1]
    return common_path, old_tail_path, new_tail_path


def get_spliced_names(old_state_name, new_state_name):
    old_path, new_path = Path(old_state_name), Path(new_state_name)
    return tuple(map(str, get_spliced_path(old_path, new_path)))


def get_spliced_paths(old_state_name, new_state_name, getter, extend=True):
    """ splits of common states from the 2 state_names """
    spliced_paths = []
    for old_path in get_expanded_paths(old_state_name, getter=getter, extend=extend):
        for new_path in get_expanded_paths(new_state_name, getter=getter, extend=extend):
            spliced_paths.append(get_spliced_path(old_path, new_path))
    return spliced_paths


def get_spliced_state_names(old_state_name, new_state_name, getter, extend=True):
    """ '.' separated names version of get_spliced_paths (turns paths into strings) """
    return [tuple(map(str, e)) for e in get_spliced_paths(old_state_name, new_state_name, getter=getter, extend=extend)]


_marker = object()


def standardize_statemachine_config(**config):
    config = copy_struct(config)

    state_listify_keys = ('on_entry', 'on_exit', 'on_stay')
    trans_listify_keys = ('old_state', 'trigger', 'on_transfer', 'condition')
    case_listify_keys = ('on_transfer', 'condition')

    def get(dct, *keys, default=_marker):
        if default is _marker:
            return tuple(dct[k] for k in keys)
        return tuple(dct.get(k, default) for k in keys)

    def state_config_getter(path):
        """ drill down """
        if isinstance(path, str):
            path = Path(path)
        state_config = config
        for state_name in path:
            state_config = state_config['states'][state_name]
        return state_config

    def states_getter(path):
        return state_config_getter(path).get('states', {})

    def initial_state(state_name):
        state_dict = states_getter(state_name)
        while state_dict:
            first_name = list(state_dict)[0]
            state_name = '.'.join([state_name, first_name])
            state_dict = state_dict[first_name].get('states')
        return state_name

    def sub_paths(state_config, path=Path()):
        states = state_config.get("states")
        if states:
            for state_name, sub_state_config in states.items():
                yield from sub_paths(sub_state_config, path + state_name)
        else:
            yield str(path)

    def listify_by_keys(dct, *keys):
        for k in keys:
            if k in dct:
                dct[k] = listify(dct[k])

    def verify_states(*state_names):
        for state_name in state_names:
            try:
                state_config_getter(state_name)
            except KeyError:
                raise MachineError(f"unknown state '{state_name}' in statemachine")
        return state_names

    def standardize_states(states_dict):
        states_dict = copy_struct(states_dict)
        for state_config in states_dict.values():
            listify_by_keys(state_config, *state_listify_keys)
        return states_dict

    def standardize_transition(transition_dict):
        transition_dicts = []

        def all_states(state_name):
            """ if there are substates, the transition will be from all these"""
            state_config = state_config_getter(state_name)
            return list(sub_paths(state_config, path=Path(state_name)))

        def append_transition(old_state, new_state, trigger, *extras):
            verify_states(old_state, new_state)
            new_state = initial_state(validate_new_state(new_state))
            new_transition = transition(old_state, new_state, trigger)
            for extra in extras:
                new_transition.update(copy_struct(extra))
            transition_dicts.append(new_transition)

        def append_same_state_transition(old_state, trigger):
            new_transition = transition(old_state, old_state, trigger,
                                        info='default transition back to same state')
            transition_dicts.append(new_transition)

        old_states = transition_dict.pop('old_state')
        new_states = transition_dict.pop('new_state')
        triggers = transition_dict.pop('trigger')

        for old_state in get_expanded_state_names(*old_states,
                                                  state_getter=states_getter):
            for full_old_state in all_states(old_state):
                for trigger in triggers:
                    if isinstance(new_states, Mapping):
                        for new_state, case in new_states.items():
                            listify_by_keys(case, *case_listify_keys)
                            append_transition(full_old_state, new_state, trigger, transition_dict, case)
                    elif isinstance(new_states, (list, tuple)):
                        for case in new_states:
                            listify_by_keys(case, *case_listify_keys)
                            append_transition(full_old_state, case.pop('state'), trigger, transition_dict, case)
                    else:
                        append_transition(full_old_state, new_states, trigger, transition_dict)
                    if transition_dicts[-1].get('condition'):
                        if transition_dicts[-1]['old_state'] == transition_dicts[-1]['new_state']:
                            raise MachineError(f"cannot generate default transition: condition on state state transition")
                        append_same_state_transition(full_old_state, trigger)
        return transition_dicts

    def pushdown_transitions(transition_dicts):
        """ moves transitions down in the nested state tree """

        def equals(trans1, trans2):
            return (trans1['old_state'] == trans2['old_state'] and
                    trans1['new_state'] == trans2['new_state'] and
                    trans1['trigger'] == trans2['trigger'])

        def get_equal(transitions, transition):
            for trans in transitions:
                if equals(trans, transition):
                    return trans
            return None

        def merge(trans1, trans2):
            if not equals(trans1, trans2):
                raise MachineError(f"cannot merge transitions with different 'old_state', 'new_state' or 'trigger'")
            if trans1['condition'] and trans2['condition']:
                raise MachineError(f"cannot merge transitions which both have conditions")
            trans1['on_transfer'] = list(trans1['on_transfer']) + list(trans2['on_transfer'])
            trans1['info'] = '; '.join([trans1['info'] + trans2['info']])
            return trans1

        for transition_dict in transition_dicts[:]:
            old_state = transition_dict.pop('old_state')
            new_state = transition_dict.pop('new_state')
            common, old_tail, new_tail = get_spliced_names(old_state, new_state)
            if len(common):
                transition_dicts.remove(transition_dict)
                state_config = state_config_getter(common)
                transition_dict.update(old_state=old_tail,
                                       new_state=new_tail)
                same_transition = get_equal(state_config['transitions'], transition_dict)
                if same_transition:
                    merge(same_transition, transition_dict)
                else:
                    state_config['transitions'].append(transition_dict)
            else:
                transition_dict.update(old_state=old_state, new_state=new_state)  # put back states

    def standardize_transitions(transition_dicts):
        new_transitions = []

        for transition_dict in transition_dicts:
            listify_by_keys(transition_dict, *trans_listify_keys)

        while len(transition_dicts):
            new_transitions.extend(standardize_transition(transition_dicts.pop(0)))

        pushdown_transitions(new_transitions)

        return validate_transitions(new_transitions)

    def validate_transitions(transition_dicts):

        def check_uniqueness(trans_dicts):
            seen_keys = set()
            for trans_dict in trans_dicts:
                unique_key = get(trans_dict, 'old_state', 'new_state', 'trigger')
                if unique_key in seen_keys:
                    raise MachineError(f"double {unique_key} transition in expanded transitions")
                seen_keys.add(unique_key)

        def check_conditionals(trans_dicts):
            triggering = defaultdict(list)
            for trans_dict in trans_dicts:
                triggering[get(trans_dict, 'old_state', 'trigger')].append(trans_dict)
            for key, transes in triggering.items():
                for trans in transes[:-1]:
                    if not trans.get("condition"):
                        raise MachineError(f"missing conditions in transitions with {key}")

                if transes[-1].get("condition"):
                    raise MachineError(f"no default for conditional transition with {key}")

        check_uniqueness(transition_dicts)
        check_conditionals(transition_dicts)
        return transition_dicts

    config_states = config.get('states')
    if config_states:
        states_dict = standardize_states(config['states'])
        transitions = standardize_transitions(config['transitions'])
        for state_name, state_config in config_states.items():
            states_dict[state_name] = standardize_statemachine_config(**state_config)
        config.update(states=states_dict, transitions=transitions)
    return config

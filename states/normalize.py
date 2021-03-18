__author__ = "lars van gemerden"

from contextlib import contextmanager
from functools import partial
from typing import Set
from collections import deque, defaultdict

from .tools import listify, Path, copy_struct
from .exception import MachineError


def validate_new_state(state_name_s):
    if '*' in state_name_s or isinstance(state_name_s, (list, tuple, Set)):
        raise MachineError(f"cannot use '*' in state name '{state_name_s}' switch, "
                           f"transitions can only have a single end-state")
    return state_name_s


def get_extended_paths(*state_names, getter, base_path=Path()):
    extended = []
    extend_queue = deque([Path(s) for s in state_names])
    while len(extend_queue):
        head_path = extend_queue.popleft()
        tail_paths = getter(head_path)
        if len(tail_paths):
            for tail_path in tail_paths:
                extend_queue.append(head_path + tail_path)
        else:
            extended.append(base_path + head_path)
    return extended


def get_expanded_paths(*state_names, getter, base_path=Path(), extend=False):
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
            if extend:
                expanded.extend(get_extended_paths(path, getter=getter, base_path=base_path))
            else:
                expanded.append(base_path + path)
        else:  # essentially replace '*' with all substates of the state pointed to by head
            for sub_state_name in getter(head):
                queue.append(head + sub_state_name + tail)
    return expanded


def get_expanded_state_names(*args, **kwargs):
    """ '.' separated names version of get_expanded_paths (turns paths into strings) """
    return [str(e) for e in get_expanded_paths(*args, **kwargs)]


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


def get_spliced_paths(old_state_name, new_state_name, getter, base_path=Path(), extend=True):
    """ splits of common states from the 2 state_names """
    spliced_paths = []
    for old_path in get_expanded_paths(old_state_name, getter=getter, base_path=base_path, extend=extend):
        for new_path in get_expanded_paths(new_state_name, getter=getter, base_path=base_path, extend=extend):
            spliced_paths.append(get_spliced_path(old_path, new_path))
    return spliced_paths


def get_spliced_state_names(*args, **kwargs):
    """ '.' separated names version of get_spliced_paths (turns paths into strings) """
    return [tuple(map(str, p)) for p in get_spliced_paths(*args, **kwargs)]


_marker = object()


def normalize_statemachine_config(**root_config):
    """
    normalizes the state-machine configuration:
     - all transitions are placed under correct state,
     - transition old_states and new_states are split into multiple transitions without wildcards and with full paths
     - all single callbacks are turned into lists of callbacks
     - extra validations

    :param root_config: configuration written by user-developer
    :return: normalized configuration
    """
    config_listify_keys = ('transitions', 'prepare')
    state_listify_keys = ('on_entry', 'on_exit', 'on_stay', 'constraint')
    trans_listify_keys = ('old_state', 'new_state', 'trigger', 'on_transfer', 'condition')
    case_listify_keys = ('new_state', 'on_transfer', 'condition')

    def listify_by_keys(dct, *keys):
        for k in keys:
            if k in dct:
                dct[k] = listify(dct[k])
        return dct

    def iter_configs(config, path=Path()):
        yield path, config
        for state_name, state_config in config.get('states', {}).items():
            yield from iter_configs(state_config, path + state_name)

    @contextmanager
    def annotated(root_config_):
        for path, config in iter_configs(root_config_):
            config['path'] = path
            config['parent'] = config_getter(path[:-1], root_config_) if path else None
        yield
        for path, config in iter_configs(root_config_):
            del config['path']
            del config['parent']

    def iter_parents(state_config):
        yield state_config
        while state_config.get('parent'):
            state_config = state_config['parent']
            yield state_config

    def config_getter(path, conf=None):
        """ move up - drill down """
        if isinstance(path, str):
            path = Path(path)
        for state_config in iter_parents(conf or root_config):
            try:
                for state_name in path:
                    state_config = state_config['states'][state_name]
                return state_config
            except KeyError:
                pass
        raise MachineError(f"state '{path}' not found in state machine")

    def state_getter(path, conf=None):
        return config_getter(path, conf).get('states', {})

    def validate_states(*states):
        for state_name in states[1:]:
            validate_new_state(state_name)
        for state_name in states:
            config_getter(state_name, root_config)
        return states

    def initial_state(state_name, conf=None):
        state_config = config_getter(state_name, conf)
        state_path = state_config['path']
        while state_config.get('states'):
            first_name = list(state_config['states'])[0]
            state_path = state_path + first_name
            state_config = state_config['states'][first_name]
        return str(state_path)

    def normalize_config(config):
        for _, state_config in iter_configs(config):
            listify_by_keys(state_config, *config_listify_keys)

    def normalize_states(config):
        for _, state_config in iter_configs(config):
            listify_by_keys(state_config.get('states', {}), *state_listify_keys)

    def normalize_transitions(config):

        def gather_transitions(config):

            def validate_transitions(transitions_dict):
                seen_keys = set()
                for transitions in transitions_dict.values():
                    for trans in transitions:
                        key = (trans['old_state'], tuple(trans['new_state']), trans['trigger'])
                        if key in seen_keys:
                            raise MachineError(f"double transition from '{key[0]}' to '{key[1]}' with trigger '{key[2]}'")
                        seen_keys.add(key)

                return transitions_dict

            def expand_transitions(state_path, state_config, transitions_dict):
                get_state = partial(state_getter, conf=state_config)

                def create_new(transition, old_state, new_states, on_transfer, case=None, **kwargs):
                    new_states = [initial_state(s, state_config) for s in new_states]
                    old_state, *new_states = validate_states(old_state, *new_states)
                    if case:
                        case = listify_by_keys(case, *case_listify_keys)
                        on_transfer = on_transfer + case.get('on_transfer', [])
                        kwargs['info'] = case.get('info', transition.get('info', ''))
                        if transition.get('condition'):
                            raise MachineError(
                                f"transition over {[old_state] + new_states} cannot have uncased 'condition' argument")
                        kwargs['condition'] = case.get('condition', [])
                    new_transition = copy_struct(transition)
                    new_transition.update(old_state=old_state, new_state=new_states, on_transfer=on_transfer, **kwargs)
                    return new_transition

                for transition in state_config.pop('transitions', ()):
                    transition = listify_by_keys(transition,
                                                 *trans_listify_keys)
                    old_states = transition.pop('old_state')
                    new_states = transition.pop('new_state')
                    triggers = transition.pop('trigger')
                    on_transfer = transition.pop('on_transfer', [])
                    for old_path in get_expanded_paths(*old_states, getter=get_state,
                                                       base_path=state_path, extend=True):
                        for trigger in triggers:
                            for state in new_states[:-1]:
                                if not isinstance(state, str):
                                    raise MachineError(f"only the last state in the transition from "
                                                       f"'{old_states}' to '{str(new_states)}' can be conditional")
                            if len(new_states) and isinstance(new_states[-1], (list, tuple)):
                                for case in new_states[-1]:
                                    new_transition = create_new(transition, str(old_path), new_states[:-1] + case['state'],
                                                                trigger=trigger, on_transfer=on_transfer, case=case)
                                    transitions_dict[old_path].append(new_transition)

                            else:
                                new_transition = create_new(transition, str(old_path), new_states,
                                                            trigger=trigger, on_transfer=on_transfer)
                                transitions_dict[old_path].append(new_transition)
                return transitions_dict

            transitions_dict = defaultdict(list)
            for state_path, state_config in iter_configs(config):
                expand_transitions(state_path, state_config, transitions_dict)
            return validate_transitions(transitions_dict)

        def inject_transitions(config, transitions_dict):
            for old_path, transitions in transitions_dict.items():
                state_config = config_getter(old_path, config)
                state_config['transitions'] = transitions

        transitions_dict = gather_transitions(config)
        inject_transitions(config, transitions_dict)

    root_config = copy_struct(root_config)
    with annotated(root_config):
        normalize_config(root_config)
        normalize_states(root_config)
        normalize_transitions(root_config)
    return root_config

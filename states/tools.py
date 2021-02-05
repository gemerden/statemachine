__author__ = "lars van gemerden"

from itertools import zip_longest
from typing import Sequence, Mapping, MutableMapping, Set

"""
These are functions to make the state machine config more readable and to to validate it
"""


def states(**state_configs):
    if not all(isinstance(s, dict) for s in state_configs.values()):
        raise MachineError(f"all states in 'states' should be of type 'dict'")
    return state_configs


def state(states=None, transitions=(), on_entry=(), on_exit=(), on_stay=(), info=""):
    if states:
        if on_stay:
            raise MachineError(f"states with nested states cannot have 'on_stay' callbacks")
        return dict(states=states, transitions=transitions,
                    on_entry=on_entry, on_exit=on_exit, info=info)
    else:
        if transitions:
            raise MachineError(f"states with no nested states cannot have transitions")
        return dict(on_entry=on_entry, on_exit=on_exit, on_stay=on_stay, info=info)


def transitions(*transitions_):
    if not all(isinstance(t, dict) for t in transitions_):
        raise MachineError(f"all transitions in 'transitions' should be of type 'dict'")
    return list(transitions_)


def transition(old_state, new_state, trigger, on_transfer=(), condition=(), info=""):
    if isinstance(new_state, Mapping) and case:
        raise MachineError(f"transitions with multiple (switched) end-states cannot have a single condition")
    return dict(old_state=old_state, new_state=new_state, trigger=trigger,
                on_transfer=on_transfer, condition=condition, info=info)


def switch(*state_conditions):
    if not all(isinstance(c, dict) for c in state_conditions):
        raise MachineError(f"all values in 'switch' must be 'dict'")
    return list(state_conditions)


def case(state, condition, on_transfer=(), info=""):
    return dict(state=state, condition=condition, on_transfer=on_transfer, info=info)


def default(state, on_transfer=(), info=""):
    return dict(state=state, condition=(), on_transfer=on_transfer, info=info)


""" ----------------------------------------------------------------------------------------- """


def copy_struct(value_or_mapping_or_sequence):
    vms = value_or_mapping_or_sequence
    try:
        if isinstance(vms, str):
            return vms
        if isinstance(vms, (Set, Sequence)):
            return type(vms)(copy_struct(v) for v in vms)
        elif isinstance(vms, Mapping):
            return type(vms)(**{k: copy_struct(v) for k, v in vms.items()})
        else:
            return type(vms)(vms)
    except TypeError:
        return vms


def listify(list_or_item):
    """utitity function to ensure an argument becomes a list if it is not one yet"""
    if isinstance(list_or_item, (list, tuple, set)):
        return list(list_or_item)
    else:
        return [list_or_item]


def nameify(f, cast=lambda v: v):
    """ tries to give a name to an item"""
    return ".".join([f.__module__, f.__name__]) if (callable(f) or isinstance(f, type)) else getattr(f, "name", cast(f))


_marker = object()


class Path(tuple):
    '''
    tuple sub-class representing a path from one object to another. There are two types of items in a path:

        1- keys: strings for lookpup of items in dictlike objects
        2- indexes: integers for lookup of items in listlike objects

    example: dct["some"][3]{"thing"] -> Path(["some", 3, "thing"]).get_in(dct)

    Path also converts to/from default '.' separated strings.

    example: Path("some.3.thing") == Path(["some", 3, "thing"])
    '''

    separator = "."

    @classmethod
    def items(cls, target, key_cast=lambda v: v, path=None):  # can be optimized
        """
        Iterates recursively over all values in the map and yields the path in the map and the nested value.

        :param target: input sequence (e.g. list) or mapping (e.g. dict)
        :param key_cast: determines how the path will be yielded; default is Path, str is a useful alternative
        :param path: path to the current element, for internally passing the path until now
        :yield: path, value pairs
        """
        path = path or Path()
        if isinstance(target, Mapping):
            for k, m in target.items():
                yield from cls.items(m, key_cast, path + k)
        elif isinstance(target, Sequence) and not isinstance(target, str):
            for i, m in enumerate(target):
                yield from cls.items(m, key_cast, path + i)
        else:
            yield key_cast(path), target

    @classmethod
    def keys(cls, target, key_cast=lambda v: v, path=None):
        for key, value in cls.items(target, key_cast, path):
            yield key

    @classmethod
    def values(cls, target, key_cast=lambda v: v, path=None):
        for key, value in cls.items(target, key_cast, path):
            yield value

    @classmethod
    def apply_all(cls, target, func):  # can be optimized
        """
        Applies func to all elements without sub elements and replaces the original with the return value of func
        """
        if isinstance(target, MutableMapping):
            for k, m in target.items():
                target[k] = cls.apply_all(m, func)
            return target
        elif isinstance(target, Sequence) and not isinstance(target, str):
            target = list(target)
            for i, m in enumerate(target):
                target[i] = cls.apply_all(m, func)
            return target
        else:
            return func(target)

    @classmethod
    def validate(cls, v):
        try:
            return int(v)
        except ValueError:
            return v

    def __new__(cls, string_s=()):
        """constructor for path; __new__ is used because objects of base class tuple are immutable"""
        if isinstance(string_s, str):
            validate = cls.validate
            string_s = (validate(s) for s in string_s.split(cls.separator) if len(s))
        return super().__new__(cls, string_s)

    def __getitem__(self, key):
        """ makes sure the slicing returns a Path object, not a tuple """
        if isinstance(key, slice):
            return self.__class__(tuple.__getitem__(self, key))
        return tuple.__getitem__(self, key)

    def has_in(self, target):
        """
        checks whether the path is present in the target argument, which can be mapping or list
         (or mapping of lists, etc)
        """
        try:
            self.get_in(target)
            return True
        except KeyError:
            return False

    def get_in(self, target, default=_marker):
        """ gets an item from the target argument, which can be mapping or list (or mapping of lists, etc)"""
        try:
            for k in self:
                try:
                    target = target[k]
                except KeyError:
                    target = target[str(k)]
            return target
        except (KeyError, IndexError, TypeError):
            if default is not _marker:
                return default
            raise

    def set_in(self, target, item):
        """ adds the item to the target argument, which can be mapping or list (or mapping of lists, etc)"""
        target = self[:-1].get_in(target)
        try:
            target[self[-1]] = item
        except KeyError:
            target[str(self[-1])] = item

    def del_in(self, target):
        """ deletes an item from the target argument, which can be mapping or list (or mapping of lists, etc)"""
        target = self[:-1].get_in(target)
        try:
            del target[self[-1]]
        except KeyError:
            del target[str(self[-1])]

    def __add__(self, p):
        """ adds 2 paths together or adds string element(s) to the path, returning a new Path object"""
        if isinstance(p, str):
            p = Path(p)
        elif isinstance(p, int):
            p = (p,)
        return Path(super(Path, self).__add__(p))

    def iter_in(self, target, include=False):
        """ iterates into the target, e.g. Path("a.b").iter_in({"a":{"b":1}}) yields {"b":1} and 1"""
        if include:
            yield target
        for key in self:
            target = target[key]
            yield target

    def iter_out(self, target, include=False):
        """ same as iter_in, but in reversed order"""
        return reversed(list(self.iter_in(target, include)))

    def iter_paths(self, cast=None):
        """ iterates over sub-paths, e.g. Path("a.b.c").iter_paths() yields Path("a"), Path("a.b"), Path("a.b.c")"""
        for i in range(1, len(self) + 1):
            yield cast(self[:i]) if cast else self[:i]

    def tail(self, path):
        """
        returns the last keys in the path, removing the keys in argument path, e.g. Path("a.b.c").tail(Path("a.b")) ->
            Path("c")
        """
        if any(k != self[i] for i, k in enumerate(path)):
            raise KeyError("cannot left strip Path, key not found")
        return self[len(path):]

    def head(self, path):
        """
        returns the first keys in the path, removing the keys in argument path, e.g. Path("a.b.c").head(Path("b.c")) ->
            Path("a")
        """
        if any(k != self[-len(path) + i] for i, k in enumerate(path)):
            raise KeyError("cannot right strip Path, key not found")
        return self[:-len(path)]

    def splice(self, other):
        self, other = Path(self), Path(other)
        common = []
        for i, (s, o) in enumerate(zip_longest(self, other)):
            if s == o:
                common.append(s)
            else:
                return Path(common), self[i:], other[i:]
        return self, Path(), Path()

    def partition(self, key):
        if not len(self):
            return Path(), key, Path()
        for i, k in enumerate(self):
            if k == key:
                return self[:i], key, self[i + 1:]
        return self[:], key, Path()

    def __repr__(self):
        """ returns the string representation:  Path("a.b.c") -> "a.b.c" """
        return self.separator.join([str(s) for s in self])


def replace_in_list(lst, old_item, new_items):
    """ replaces single old_item with a list new_item(s), retaining order of new_items """
    new_items = listify(new_items)
    index = lst.index(old_item)
    lst.remove(old_item)
    for i, item in enumerate(new_items):
        lst.insert(index + i, item)
    return lst


def has_doubles(lst):  # slow, O(n^2)
    return any(lst.count(l) > 1 for l in lst)


class lazy_property(object):
    """A read-only @property that is only evaluated once."""

    def __init__(self, getter):
        self.getter = getter
        self.name = getter.__name__
        self.__doc__ = getter.__doc__

    def __get__(self, obj, cls):
        if obj is None:
            return self
        obj.__dict__[self.name] = result = self.getter(obj)
        return result


class MachineError(ValueError):
    """Exception indicating an error in the construction of the state machine"""
    pass


class TransitionError(ValueError):
    """Exception indicating an error in the in a state transition of an object"""
    pass

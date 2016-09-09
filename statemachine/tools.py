from collections import Sequence, Mapping

__author__ = "lars van gemerden"


def listify(list_or_item):
    """utitity function to ensure an argument becomes a list if it is not one yet"""
    if isinstance(list_or_item, (list, tuple, set)):
        return list(list_or_item)
    else:
        return [list_or_item]


def callbackify(callbacks):
    """
    Turns one or multiple callback functions or their names into one callback functions. Names will be looked up on the
    first argument (obj) of the actual call to the callback.

    :param callbacks: single or list of functions or method names, all with the same signature
    :return: new function that performs all the callbacks when called
    """
    callbacks = listify(callbacks)

    def result_callback(obj, *args, **kwargs):
        for callback in callbacks:
            if isinstance(callback, str):
                return getattr(obj, callback)(*args, **kwargs)
            else:
                return callback(obj, *args, **kwargs)

    return result_callback


def nameify(f, cast=lambda v: v):
    """ tries to give a name to an item"""
    return ".".join([f.__module__, f.__name__]) if callable(f) else getattr(f, "name", cast(f))


def clean_dict(dct):
    """ removes items evaluating to False from dictionary """
    for k, v in dct.copy().iteritems():
        if not v:
            del dct[k]
    return dct

def replace_in_list(lst, old_item, new_items):
    """ replaces single old_item with a list new_item(s), retaining order of new_items """
    new_items = listify(new_items)
    index = lst.index(old_item)
    lst.remove(old_item)
    for i, item in enumerate(new_items):
        lst.insert(index+i, item)
    return lst


def has_doubles(lst):  # slow, O(n^2)
    return any(lst.count(l) > 1 for l in lst)

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
    def iter_all(cls, map, key_cast=lambda v: v, path=None):  # can be optimized
        """
        Iterates recursively over all values in the map and yields the path in the map and the nested value.

        :param map: input sequence (e.g. list) or mapping (e.g. dict)
        :param key_cast: determines how the path will be yielded; default is Path, str is a useful alternative
        :param path: path to the current element, for internally passing the path until now
        :yield: path, value pairs
        """
        path = path or Path()
        if isinstance(map, Mapping):
            for k, m in map.iteritems():
                for path_value in cls.iter_all(m, key_cast, path+k):
                    yield path_value
        elif isinstance(map, Sequence) and not isinstance(map, basestring):
            for i, m in enumerate(map):
                for path_value in cls.iter_all(m, key_cast, path+i):
                    yield path_value
        else:
            yield key_cast(path), map

    @classmethod
    def apply_all(cls, map, func):  # can be optimized
        """
        Applies func to all elements without sub elements and replaces the original with the return value of func
        """
        if isinstance(map, Mapping):
            for k, m in map.iteritems():
                map[k] = cls.apply_all(m, func)
            return map
        elif isinstance(map, Sequence) and not isinstance(map, basestring):
            for i, m in enumerate(map):
                map[i] = cls.apply_all(m, func)
            return map
        else:
            return func(map)

    @classmethod
    def validate(cls, v):
        try:
            return int(v)
        except ValueError:
            return v

    def __new__(cls, string_s=()):
        """constructor for path; __new__ is used because objects of base class tuple are immutable"""
        if isinstance(string_s, str):
            val = cls.validate
            string_s = (val(s) for s in string_s.split(cls.separator))
        return super(Path, cls).__new__(cls, string_s)

    def __getslice__(self, i, j):
        """ makes sure the slicing returns a Path object, not a tuple"""
        return Path(super(Path, self).__getslice__(i, j))

    def has_in(self, map):
        """
        checks whether the path is present in the map argument, which can be mapping or list
         (or mapping of lists, etc)
        """
        try:
            self.get_in(map)
            return True
        except KeyError:
            return False

    def get_in(self, map, default=_marker):
        """ gets an item from the map argument, which can be mapping or list (or mapping of lists, etc)"""
        try:
            for k in self:
                try:
                    map = map[k]
                except KeyError:
                    map = map[str(k)]
            return map
        except (KeyError, IndexError, TypeError):
            if default is not _marker:
                return default
            raise

    def set_in(self, map, item):
        """ adds the item to the map argument, which can be mapping or list (or mapping of lists, etc)"""
        map = self[:-1].get_in(map)
        try:
            map[self[-1]] = item
        except KeyError:
            map[str(self[-1])] = item

    def del_in(self, map):
        """ deletes an item from the map argument, which can be mapping or list (or mapping of lists, etc)"""
        map = self[:-1].get_in(map)
        try:
            del map[self[-1]]
        except KeyError:
            del map[str(self[-1])]

    def __add__(self, p):
        """ adds 2 paths together or adds string element(s) to the path, returning a new Path object"""
        if isinstance(p, str):
            p = Path(p)
        elif isinstance(p, int):
            p = (p,)
        return Path(super(Path, self).__add__(p))

    def iter_in(self, map):
        """ iterates into the map, e.g. Path("a.b").iter_in({"a":{"b":1}}) yields {"b":1} and 1"""
        for key in self:
            map = map[key]
            yield map

    def iter_out(self, map):
        """ same as iter_in, but in reversed order"""
        return reversed(list(self.iter_in(map)))

    def iter_paths(self, cast=None):
        """ iterates over sub-paths, e.g. Path("a.b.c").iter_paths() yields Path("a"), Path("a.b"), Path("a.b.c")"""
        for i in range(1, len(self)+1):
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
        if any(k != self[-len(path)+i] for i, k in enumerate(path)):
            raise KeyError("cannot right strip Path, key not found")
        return self[:-len(path)]

    def __repr__(self):
        """ returns the string representation:  Path("a.b.c") -> "a.b.c" """
        return self.separator.join([str(s) for s in self])



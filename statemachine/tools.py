__author__ = "lars van gemerden"


def listify(list_or_item):
    """utitity function to ensure an argument becomes a list if it is not one yet"""
    if isinstance(list_or_item, (list, tuple)):
        return list(list_or_item)
    else:
        return [list_or_item]


def callbackify(callbacks):
    """
    turns one or multiple callback functions or their names into one callback functions. Names will be looked up on the
    first argument of the actual call to the callback.

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
    def try_int(cls, v):
        try:
            return int(v)
        except ValueError:
            return v

    def __new__(cls, string_s):
        """constructor for path; __new__ is used because baseclass tuple is immutable"""
        if isinstance(string_s, str):
            dec = cls.try_int
            string_s = (dec(s) for s in string_s.split(cls.separator))
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

    def get_in(self, map):
        """ gets an item from the map argument, which can be mapping or list (or mapping of lists, etc)"""
        for k in self:
            try:
                map = map[k]
            except KeyError:
                map = map[str(k)]
        return map

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

    def __add__(self, v):
        """ adds 2 paths together or adds a string to the path, returning a new Path object"""
        if isinstance(v, str):
            v = Path(v)
        return Path(super(Path, self).__add__(v))

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
        return self.separator.join(self)



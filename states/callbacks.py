__author__ = "lars van gemerden"

import json
from typing import Mapping

from states.tools import listify


class NoFunction(object):
    def __call__(self, *args, **kwargs):
        return True

    def __bool__(self):
        return False


nofunction = NoFunction()


class Callbacks(Mapping):

    @classmethod
    def _validate_name(cls, name):
        if name.startswith('_'):
            raise ValueError(f"callback name '{name}' cannot start with '_'")
        if hasattr(cls, name):
            raise ValueError(f"cannot name callback '{name}': name is reserved")
        return name

    @classmethod
    def _name_function(cls, f):
        """ intended to make sensible strings from functions """
        if callable(f) or isinstance(f, type):
            name = f.__qualname__
            if '.' in name:
                return ".".join(name.split('.')[-2:])
            return ".".join((f.__module__, name))
        else:
            return f  # string

    def __init__(self, **callbacks):
        self._callbacks = {}
        for name, callback_s in callbacks.items():
            name = self._validate_name(name)
            self._callbacks[name] = listify(callback_s)
        self._function_cache = {}

    def resolve(self, cls):
        for callbacks in self._callbacks.values():
            for i, callback in enumerate(callbacks):
                if isinstance(callback, str):
                    callbacks[i] = getattr(cls, callback)

    def _create_function(self, name):
        try:
            callbacks = self._callbacks[name]
        except KeyError:
            raise AttributeError(f"no callbacks '{name}' found")

        if len(callbacks) == 0:
            call = nofunction  # works as callbacks, but bool(nofunction) == False, for filtering when optimizing
        elif len(callbacks) == 1:
            call = callbacks[0]
        else:
            def call(obj, *args, **kwargs):
                result = True
                for callback in callbacks:
                    if callback(obj, *args, **kwargs) is False:
                        result = False
                return result
        call.__name__ = name
        return call

    def __getattr__(self, name):
        try:
            return self._function_cache[name]
        except KeyError:
            result = self._function_cache[name] = self._create_function(name)
            return result

    def __len__(self):
        return len(self._callbacks)

    def __iter__(self):
        yield from self._callbacks

    def __getitem__(self, key):
        return self._callbacks[key]

    def register(self, **callbacks):
        for name, callback in callbacks.items():
            self._callbacks[name].extend(listify(callback))
        self._clear_cache(*callbacks)

    def _clear_cache(self, *names):
        if len(names):
            for name in names:
                self._function_cache.pop(name, None)
        else:
            self._function_cache.clear()

    def as_json_dict(self):
        return {k: list(map(self._name_function, c)) for k, c in self._callbacks.items() if len(c)}

    def __repr__(self):
        return json.dumps(self.as_json_dict(), indent=4)


if __name__ == '__main__':
    pass

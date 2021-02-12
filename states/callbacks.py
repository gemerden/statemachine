__author__ = "lars van gemerden"

import json

from states.tools import listify


def _nameify(f):
    if callable(f) or isinstance(f, type):
        name = f.__qualname__
        if '.' in name:
            return ".".join(name.split('.')[-2:])
        return ".".join((f.__module__, name))
    else:
        return f  # string


class Callbacks(object):

    def __init__(self, **callbacks):
        self._callbacks = {}
        self._functions = {}
        for name, callback_s in callbacks.items():
            name = name.strip()
            self._callbacks[name] = listify(callback_s)
            self._functions[name] = self._get_func(name)

    def _get_func(self, name):
        callbacks = self._callbacks[name]

        def call(obj, *args, __name=name, **kwargs):
            results = []
            for callback in callbacks:
                if isinstance(callback, str):
                    results.append(getattr(obj, callback)(*args, **kwargs))
                else:
                    results.append(callback(obj, *args, **kwargs))
            return all(results)

        call.__name__ = name
        return call

    def __getattr__(self, name):
        try:
            return self._functions[name]
        except KeyError:
            raise AttributeError(f"no callbacks '{name}' found")

    def register(self, name, *callback_s):
        self._callbacks[name.strip()].extend(callback_s)

    def has_any(self, name):
        return bool(self._callbacks.get(name.strip(), None))

    def copy(self):
        return self.__class__(**{k: c[:] for k, c in self._callbacks.items()})

    def as_json_dict(self):
        return {k: list(map(_nameify, c)) for k, c in self._callbacks.items() if len(c)}

    def __repr__(self):
        return json.dumps(self.as_json_dict(), indent=4)


if __name__ == '__main__':
    pass

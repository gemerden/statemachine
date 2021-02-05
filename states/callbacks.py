from functools import partial
from operator import attrgetter

from states.tools import listify


class Callbacks(object):
    name_prefix = '_'
    func_prefix = 'do_'

    def __init__(self, **callbacks):
        for name, callback_s in callbacks.items():
            attr_name = self.name_prefix + name
            func_name = self.func_prefix + name
            setattr(self, attr_name, listify(callback_s))
            setattr(self, func_name, self._get_func(attr_name))

    def _get_func(self, name):
        callbacks = getattr(self, name)

        def call(obj, *args, **kwargs):
            results = []
            for callback in callbacks:
                if isinstance(callback, str):
                    results.append(getattr(obj, callback)(*args, **kwargs))
                else:
                    results.append(callback(obj, *args, **kwargs))
            return all(results)

        call.__name__ = name
        return call

    def _register(self, name, *callbacks):
        getattr(self, self.name_prefix + name).extend(callbacks)


if __name__ == '__main__':
    class Some(object):
        def do_it(self, *args, **kwargs):
            print('done')


    def fly_it(*args, **kwargs):
        print('flone')


    cb = Callbacks(on_entry=('do_it', fly_it))
    cb._on_entry.append('do_it')

    cb.do_on_entry(Some())

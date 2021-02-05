from states.tools import listify


class Callbacks(object):
    name_prefix = '_'
    func_prefix = ''

    def __init__(self, **callbacks):
        for name, callback_s in callbacks.items():
            attr_name = self.name_prefix + name
            func_name = self.func_prefix + name
            setattr(self, attr_name, listify(callback_s))
            setattr(self, func_name, self._get_func(attr_name))

    def register(self, name, *callback_s):
        getattr(self, self.name_prefix + name).extend(callback_s)

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







if __name__ == '__main__':
    pass
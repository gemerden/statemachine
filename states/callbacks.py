from states.tools import listify


class Callbacks(object):
    attr_prefix = '_'
    func_prefix = ''

    def __init__(self, **callbacks):
        for name, callback_s in callbacks.items():
            attr_name = self.attr_prefix + name
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

    def has_any(self, name):
        return bool(len(getattr(self, self.attr_prefix + name, ())))

    def register(self, name, *callback_s):
        getattr(self, self.attr_prefix + name).extend(callback_s)

    def copy(self):
        callbacks = {}
        for name, value in self.__dict__.items():
            if name.startswith(self.attr_prefix) and isinstance(value, list) :
                callbacks[name.lstrip(self.attr_prefix)] = value[:]
        return self.__class__(**callbacks)





if __name__ == '__main__':
    pass
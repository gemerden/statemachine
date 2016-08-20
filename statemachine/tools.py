def listify(list_or_item):
    """utitity function to ensure an argument becomes a list if it is not one yet"""
    if isinstance(list_or_item, (list, tuple)):
        return list(list_or_item)
    else:
        return [list_or_item]


def lookup(name, *namespaces):
    for namespace in namespaces:
        try:
            return getattr(namespace, name)
        except AttributeError:
            pass
    raise AttributeError("lookup did not find name '5s'" % name)


def callbackify(callbacks):
    """if present lookup strings callbacks in namespaces (looking in given orden)"""
    callbacks = listify(callbacks)

    def result_callback(obj, *args, **kwargs):
        for callback in callbacks:
            if isinstance(callback, str):
                getattr(obj, callback)(*args, **kwargs)
            else:
                callback(obj, *args, **kwargs)

    return result_callback


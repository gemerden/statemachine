import random

from collections import defaultdict

from statemachine.machine import StateMachine, StatefulObject

class Registered(object):
    
    @classmethod
    def register(cls, item):
        if "_reg" not in cls.__dict__:
            cls._reg = {}
        if item.name in cls._reg:
            raise ValueError("name '%s' already in class '%s'" % (item.name, cls.__name__))
        cls._reg[item.name] = item

    @classmethod
    def remove(cls, item):
        del cls._reg[item.name]

    @classmethod
    def get(cls, name):
        return cls._reg[name]

    @classmethod
    def all(cls, flt):
        return cls._reg.values()

    @classmethod
    def filter(cls, flt):
        return [r for r in cls._reg.itervalues() if flt(r)]

    @classmethod
    def random(cls, flt=lambda v: True):
        return random.choice(cls.filter(flt))

    def __init__(self, name, *args, **kwargs):
        super(Registered, self).__init__(*args, **kwargs)
        self.name = name
        self.__class__.register(self)


class Person(StatefulObject, Registered):

    machine = StateMachine(
        states=[
            {"name": "happy", "on_entry": []},
            {"name": "neutral", "on_entry": []},
            {"name": "angry", "on_entry": []},
        ],
        transitions=[
            {"old_state": "happy", "new_state": "neutral", "triggers": ["talk"], "condition": "update_happy"},
            {"old_state": "neutral", "new_state": "angry", "triggers": ["talk"], "condition": "update_neutral"},
            {"old_state": "angry", "new_state": "neutral", "triggers": ["talk"], "condition": "update_angry"},
            {"old_state": "neutral", "new_state": "happy", "triggers": ["talk"], "condition": "update_neutral"},
        ],
        after_any_entry="tell"
    )

    def __init__(self, sensitivity, mood=1.0, *args, **kwargs):
        super(Person, self).__init__(*args, **kwargs)
        self.sensitivity = sensitivity
        self.mood = mood
        self.relations = defaultdict(int)

    def tell(self, *args, **kwargs):
        print("%s says: I'm %s" % (self.name, self.state))

    def update_happy(self, person, *args, **kwargs):
        delta_mood = self.sensitivity * self.relations[person.name]
        self.mood = max(0.0, min(1.0, self.mood + delta_mood))









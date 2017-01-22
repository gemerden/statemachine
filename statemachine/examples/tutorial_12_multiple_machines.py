from statemachine.machine import state_machine, StatefulObject


class Room(StatefulObject):

    machine = state_machine(
        states=[
            {"name": "empty", "on_entry": ["write_left", "turn_off_lights"], "condition": "is_empty"},
            {"name": "occupied", "on_entry": ["write_entered", "turn_on_lights"]},
        ],
        transitions=[
            {"old_state": "*", "new_state": "occupied", "triggers": "enter"},
            {"old_state": "occupied", "new_state": "empty", "triggers": "exit"},
        ]
    )

    def __init__(self, name, lights=None):
        super(Room, self).__init__()
        self.name = name
        self.lights = lights or []
        self.people = 0

    def turn_on_lights(self, **kwargs):
        for light in self.lights:
            if light.state == "off":
                light.turn_on(room=self)

    def turn_off_lights(self, **kwargs):
        for light in self.lights:
            if light.state == "on":
                light.turn_off(room=self)

    def enter(self, person, **kwargs):
        self.people += 1
        if person.room:
            person.room.exit(person=person)
        person.room = self
        self.machine.trigger(self, "enter", person=person, **kwargs)

    def exit(self, **kwargs):
        self.people -= 1
        self.machine.trigger(self, "exit", **kwargs)

    def is_empty(self, **kwargs):
        return self.people == 0

    def write_left(self, **kwargs):
        print("The %s is now empty" % self.name)

    def write_entered(self, person, **kwargs):
        print("%s just entered the %s" % (person.name, self.name))


class Person(object):

    def __init__(self, name):
        super(Person, self).__init__()
        self.name = name
        self.room = None


class Light(StatefulObject):

    machine = state_machine(
        states=[
            {"name": "off", "on_entry": "write"},
            {"name": "on", "on_entry": "write"},
        ],
        transitions=[
            {"old_state": "off", "new_state": "on", "triggers": "turn_on"},
            {"old_state": "on", "new_state": "off", "triggers": "turn_off"},
        ],
    )

    def __init__(self, name):
        super(Light, self).__init__()
        self.name = name

    def write(self, room, **kwargs):
        print("{light} in {room} turned {state}".format(light=self.name,
                                                        room=room.name,
                                                        state=self.state))


if __name__ == "__main__":

    living = Room("living room", lights=[Light("ceiling lamp")])
    bedroom = Room("bed room", lights=[Light("bed lamp")])
    kitchen = Room("kitchen", lights=[Light("sink light"), Light("ceiling lamp")])

    Ann = Person("Ann")
    Bob = Person("Bob")

    living.enter(person=Ann)
    print '-'
    living.enter(person=Bob)
    print '-'
    kitchen.enter(person=Ann)
    print '-'
    bedroom.enter(person=Bob)
    print '-'
    bedroom.enter(person=Ann)






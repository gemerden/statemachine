from statemachine.machine import StateMachine, StatefulObject


class Room(StatefulObject):

    machine = StateMachine(
        states=[
            {"name": "empty", "on_entry": "turn_off_lights"},
            {"name": "occupied", "on_entry": ["set_room", "turn_on_lights"]},
        ],
        transitions=[
            {"old_state": "empty", "new_state": "occupied", "triggers": "enter"},
            {"old_state": "occupied", "new_state": "occupied", "triggers": "enter"},
            {"old_state": "occupied", "new_state": "empty", "triggers": "exit", "condition": "one_left"},
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

    def set_room(self, person, **kwargs):
        person.set_room(self)

    def one_left(self, **kwargs):
        return self.people == 0


class Person(object):

    def __init__(self, name):
        super(Person, self).__init__()
        self.name = name
        self.room = None

    def set_room(self, room):
        if self.room:
                self.room.people -= 1
                self.room.exit(person=self)
                if room != self.room:
                    print("{person} went from {room1} to {room2}.".format(person=self.name,
                                                                          room1=self.room.name,
                                                                          room2=room.name))
        else:
            print("{person} entered {room}.".format(person=self.name,
                                                    room=room.name))
        room.people += 1
        self.room = room


class Light(StatefulObject):

    machine = StateMachine(
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
        print("Light {light} in {room} turned {state}.".format(light=self.name,
                                                               room=room.name,
                                                               state=self.state))


if __name__ == "__main__":

    living = Room("living", lights=[Light("shade"), Light("ceiling")])
    bedroom = Room("bedroom", lights=[Light("bedlamp 1"), Light("bedlamp 2")])
    kitchen = Room("kitchen", lights=[Light("sink"), Light("ceiling")])

    Ann = Person("Ann")
    Bob = Person("Bob")

    living.enter(person=Ann)
    living.enter(person=Bob)
    kitchen.enter(person=Ann)
    bedroom.enter(person=Bob)
    bedroom.enter(person=Ann)






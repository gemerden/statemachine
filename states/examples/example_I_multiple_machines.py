from states import StateMachine
from states import StatefulObject


class Room(StatefulObject):

    state = StateMachine(
        states={
            "empty": {"on_entry": ["turn_off_lights", "write_empty"]},
            "occupied": {"on_entry": ["turn_on_lights", "write_occupied"],
                         "on_stay": "write_occupied"},
        },
        transitions=[
            {"old_state": "*", "new_state": "occupied", "trigger": "enter", "on_transfer": "increment"},
            {"old_state": "occupied", "new_state": {"empty": {"condition": "becomes_empty"},
                                                    "occupied":{}},
             "trigger": "leave"},
        ]
    )

    def __init__(self, name, lights=()):
        super(Room, self).__init__()
        self.name = name
        self.lights = lights
        self.people = set()

    def turn_on_lights(self, person, **kwargs):
        for light in self.lights:
            light.turn_on(room=self, person=person)

    def turn_off_lights(self, person, **kwargs):
        for light in self.lights:
            light.turn_off(room=self, person=person)

    def increment(self, person, **kwargs):
        self.people.add(person)

    def becomes_empty(self, person, **kwargs):
        self.people.remove(person)
        return len(self.people) == 0

    def write_empty(self, **kwargs):
        print(f"The {self.name} is now empty")

    def write_occupied(self, person, **kwargs):
        print(f"{' and '.join(p.name for p in self.people)} {'is' if len(self.people) < 2 else 'are'} in the {self.name}")


class Person(StatefulObject):

    state = StateMachine(
        states={
            "outside": {"on_entry": "leave_room"},
            "inside": {"on_entry": "enter_room"},
        },
        transitions=[
            {"old_state": "outside", "new_state": "inside", "trigger": "enter"},
            {"old_state": "inside", "new_state": "outside", "trigger": "leave"},
        ]
    )

    def __init__(self, name):
        super(Person, self).__init__()
        self.name = name
        self.room = None
        
    def enter_room(self, room):
        self.room = room
        room.enter(person=self)

    def leave_room(self, room):
        self.room = None
        room.leave(person=self)


class Light(StatefulObject):

    state = StateMachine(
        states={
            "off": {"on_entry": "write"},
            "on": {"on_entry": "write"},
        },
        transitions=[
            {"old_state": "off", "new_state": "on", "trigger": "turn_on"},
            {"old_state": "on", "new_state": "off", "trigger": "turn_off"},
        ],
    )

    def __init__(self, name):
        super().__init__()
        self.name = name

    def write(self, room, person, **kwargs):
        print(f"{person.name} turned the {self.name} in {room.name} {self.state}")


if __name__ == "__main__":

    living = Room("living room", lights=[Light("ceiling lamp")])
    bedroom = Room("bedroom", lights=[Light("bed lamp")])
    kitchen = Room("kitchen", lights=[Light("sink light"), Light("ceiling lamp")])

    Ann = Person("Ann")
    Bob = Person("Bob")

    Ann.enter(room=living)
    Bob.enter(room=living)
    Ann.leave(room=living)
    Ann.enter(room=kitchen)
    Bob.leave(room=living)
    Ann.leave(room=kitchen)
    Bob.enter(room=bedroom)
    Ann.enter(room=bedroom)






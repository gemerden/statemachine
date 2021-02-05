from states import StateMachine, StatefulObject
from states.tools import states, state, transition, switch, condition


class Room(StatefulObject):
    state = StateMachine(
        states=states(
            empty=state(on_entry=["turn_off_lights", "write_empty"]),
            occupied=state(on_entry=["turn_on_lights", "write_occupied"],
                           on_stay="write_occupied")
        ),
        transitions=[
            transition('*', "occupied", trigger='enter', on_transfer='increment'),
            transition('occupied', switch(empty=condition("becomes_empty"),
                                          occupied=condition()),
                       trigger='leave')
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

    def write_occupied(self, **kwargs):
        print(f"{' and '.join(p.name for p in self.people)} {'is' if len(self.people) < 2 else 'are'} in the {self.name}")


class Person(StatefulObject):
    state = StateMachine(
        states=states(
            outside=state(on_entry="leave_room"),
            inside=state(on_entry="enter_room"),
        ),
        transitions=[
            transition("outside", "inside", trigger="enter"),
            transition("inside", "outside", trigger="leave"),
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
        states=states(
            off=state(on_entry="write"),
            on=state(on_entry="write"),
        ),
        transitions=[
            transition("off", "on", trigger="turn_on"),
            transition("on", "off", trigger="turn_off"),
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






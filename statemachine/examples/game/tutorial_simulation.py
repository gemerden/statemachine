import os, random

import pygame
from pygame.locals import *

from statemachine.machine import StatefulObject, StateMachine
from statemachine.tools import toss


class PygameImages(dict):

    def __init__(self, names=(), folder_name="data", ext=".png", colorkey=None):
        super(PygameImages, self).__init__()
        self.folder_name = folder_name
        self.ext = ext
        self.colorkey = colorkey
        for name in names:
            self.load(name)

    def load(self, name):
        filename = name.replace(".", "_") + self.ext
        fullname = os.path.join(self.folder_name, filename)
        try:
            image = pygame.image.load(fullname)
        except Exception as e:
            print 'Cannot load image:', fullname
            raise SystemExit(e)
        # image = image.convert()
        if self.colorkey is not None:
            if self.colorkey is -1:
                image.set_colorkey(image.get_at((0, 0)))
            else:
                image.set_colorkey(self.colorkey)
        self[name] = (image, image.get_rect())


class Cell(object):

    moves = ((1,0), (0,1), (-1,0), (0,-1))

    def __init__(self, board, x, y, piece=None):
        self.board = board
        self.x = x
        self.y = y
        self.piece = piece

    @property
    def piece(self):
        return self._piece

    @piece.setter
    def piece(self, piece):
        if piece:
            if piece.cell:
                piece.cell.piece = None
            piece.cell = self
        self._piece = piece

    def adjacent(self):
        for dx, dy in self.moves:
            try:
                piece = self.board[self.x+dx, self.y+dy]
                if piece:
                    yield piece
            except IndexError:
                pass

    def is_free(self, dx=0, dy=0):
        try:
            return self.board[self.x+dx, self.y+dy] is None
        except IndexError:
            return False

    def move_piece(self, dx, dy):
        if self.is_free(dx, dy):
            self.board[self.x+dx, self.y+dy] = self.piece
            return True
        return False

    def random_move(self):
        free = [m for m in self.moves if self.is_free(*m)]
        if len(free):
            move = random.choice(free)
            return self.move_piece(*move)
        return False

    def screen_pos(self, step):
        return self.x * step, self.y * step

    def draw(self, surface):
        if self.piece:
            self.piece.draw(surface)


class Board(object):

    def __init__(self, width, height, pieces=()):
        super(Board, self).__init__()
        self.max_x = width-1
        self.max_y = height-1
        self.cells = [[Cell(self, x, y) for y in range(height)] for x in range(width)]
        self.set_pieces(pieces)

    def size(self):
        return self.max_x + 1, self.max_y + 1

    def __getitem__(self, xy):
        return self.cells[xy[0]][xy[1]].piece

    def __setitem__(self, xy, piece):
        self.cells[max(0, min(self.max_x, xy[0]))][max(0, min(self.max_y, xy[1]))].piece = piece

    def draw(self, surface):
        for row in self.cells:
            for cell in row:
                cell.draw(surface)

    def pieces(self):
        for row in self.cells:
            for cell in row:
                if cell.piece:
                    yield cell.piece

    def update(self):
        for row in self.cells:
            for cell in row:
                if cell.piece:
                    cell.piece.update()

    def set_pieces(self, pieces):
        for piece in pieces:
            cell = self.cells[random.randint(0, self.max_x)][random.randint(0, self.max_y)]
            while cell.piece:
                cell = self.cells[random.randint(0, self.max_x)][random.randint(0, self.max_y)]
            cell.piece = piece



class Setup(object):

    step = 32
    width, height = 10, 10
    piece_count = 10
    pygame.init()
    screen = pygame.display.set_mode((width * step, height * step))
    images = PygameImages(folder_name="data", ext=".png")
    font = pygame.font.Font(None, 12)
    clock = pygame.time.Clock()
    black = (5, 5, 5)
    white = (250, 250, 250)


class Sprite(Setup, pygame.sprite.Sprite):

    def __init__(self, images, *args, **kwargs):
        super(Sprite, self).__init__(*args, **kwargs)
        for image in images:
            self.images.load(image)
        self.image, self.rect = self.images[images[0]]
        self.text = self.font.render("", True, self.black)
        self.text_rect = self.text.get_rect()

    def set_image(self, *args, **kwargs):
        rect = self.rect
        self.image, _ = self.images[self.state]
        self.rect = rect

    def set_text(self, text, *args, **kwargs):
        self.text = self.font.render(text, True, self.black)
        self.text_rect = self.text.get_rect()
        ref_point = self.rect.topright
        self.text_rect.bottomleft = (ref_point[0]+self.step/2, ref_point[1]+self.step/2)

    def draw(self, surface):
        surface.blit(self.image, self.rect)
        surface.blit(self.text, self.text_rect)


def react(text):
    def inner(obj, *args, **kwargs):
        obj.set_text(text, *args, **kwargs)
    return inner


class Piece(StatefulObject, Sprite):

    machine = StateMachine(
        states=[
            {"name": "happy", "on_entry": ["set_image", react("yippie")], "condition": "has_good_mood"},
            {"name": "normal", "on_entry": ["set_image", react("meh")], "condition": "has_normal_mood"},
            {"name": "angry", "on_entry": ["set_image", react("GRRH")], "condition": "has_bad_mood"},
        ],
        transitions=[
            {"old_state": "happy", "new_state": "*", "triggers": "evaluate_state"},
            {"old_state": "normal", "new_state": "*", "triggers": "evaluate_state"},
            {"old_state": "angry", "new_state": "*", "triggers": "evaluate_state"},
        ],
    )

    def __init__(self, mood=0.5, *args, **kwargs):
        super(Piece, self).__init__(images=self.machine.sub_states.keys(), *args, **kwargs)
        self.mood = mood
        self.cell = None

    def update(self):
        if self.move():
            for piece in self.cell.adjacent():
                self.interact(other=piece)
            self.rect.topleft = self.cell.screen_pos(self.step)

    def move(self, dx=None, dy=None):
        if dx is None and dy is None:
            success = self.cell.random_move()
        else:
            success = self.cell.move_piece(dx, dy)
        return success

    def interact(self, other):
        if toss(0.8):
            self.talk(other=other, text="hi")
        elif toss(0.5):
            self.please(other=other, text="hi, love")
        else:
            self.annoy(other=other, text="hiiiiiii")

    def please(self, other, text, *args, **kwargs):
        self.set_text(text)
        other._update_mood(random.random()*0.2)
        other.evaluate_state(other=self, *args, **kwargs)

    def talk(self, other, text, *args, **kwargs):
        self.set_text(text)
        other._update_mood(random.random() * 0.2 - 0.1)
        other.evaluate_state(other=self, *args, **kwargs)

    def annoy(self, other, text, *args, **kwargs):
        self.set_text(text)
        other._update_mood(random.random() * -0.2)
        other.evaluate_state(other=self, *args, **kwargs)

    def _update_mood(self, inc_mood):
        self.mood = max(0.0, min(1.0, self.mood + inc_mood))

    def has_good_mood(self, *args, **kwargs):
        return self.mood > 0.8

    def has_normal_mood(self, *args, **kwargs):
        return 0.2 < self.mood < 0.8

    def has_bad_mood(self, *args, **kwargs):
        return self.mood < 0.2


class Simulator(Setup):

    def __init__(self, board, background=(200, 200, 200)):
        self.board = board
        self.sprites = pygame.sprite.RenderPlain(list(board.pieces()))
        self.surface = pygame.Surface(self.screen.get_size()).convert()
        self.surface.fill(background)

    def run(self):
        while True:
            self.clock.tick(4)
            if not self._handle_events():
                return
            self.board.update()
            self._draw()

    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == QUIT:
                return False
        return True

    def _draw(self):
        self.screen.blit(self.surface, (0, 0))
        self.board.draw(self.screen)
        pygame.display.flip()


if __name__ == "__main__":

    pieces = [Piece() for _ in range(Setup.piece_count)]
    board = Board(Setup.width, Setup.height, pieces)
    simulator = Simulator(board)
    simulator.run()




import random
import unittest

from states.machine import replace_in_list, has_doubles
from states.tools import Path

__author__  = "lars van gemerden"

class PathTest(unittest.TestCase):

    def setUp(self):
        self.mapping = dict(
            a=1,
            b=dict(
                c=2,
                d=dict(
                    e=3
                ),
            ),
            f=[4, 5]
        )

    def test_slicing(self):
        path = Path("a.b.c.d.e")
        self.assertEqual(str(path[1]), 'b')
        self.assertEqual(str(path[1:2]), 'b')
        self.assertEqual(str(path[:-1]), 'a.b.c.d')
        self.assertEqual(str(path[-1:]), 'e')
        self.assertEqual(str(path[:]), 'a.b.c.d.e')

    def test_get_in(self):
        self.assertEqual(Path("a").get_in(self.mapping), 1)
        self.assertEqual(Path("b.c").get_in(self.mapping), 2)
        self.assertEqual(Path("b.d.e").get_in(self.mapping), 3)

    def test_set_in(self):
        Path("a").set_in(self.mapping, 4)
        Path("b.c").set_in(self.mapping, 5)
        Path("b.d.e").set_in(self.mapping, 6)
        self.assertEqual(Path("a").get_in(self.mapping), 4)
        self.assertEqual(Path("b.c").get_in(self.mapping), 5)
        self.assertEqual(Path("b.d.e").get_in(self.mapping), 6)

    def test_del_in(self):
        Path("a").del_in(self.mapping)
        Path("b.c").del_in(self.mapping)
        Path("b.d.e").del_in(self.mapping)
        Path("f").del_in(self.mapping)
        self.assertEqual(self.mapping, dict(b=dict(d=dict())))

    def test_with_list(self):
        Path("b.f").set_in(self.mapping, [4, 5, 6])
        self.assertEqual(Path("b.f.1").get_in(self.mapping), 5)
        Path("b.f.1").del_in(self.mapping)
        self.assertEqual(Path("b.f.1").get_in(self.mapping), 6)

    def test_iter_paths(self):
        path = Path("a.b.c.d")
        paths = [s for s in path.iter_paths(str)]
        self.assertEqual(paths, ['a', 'a.b', 'a.b.c', 'a.b.c.d'])

    def test_strip(self):
        path = Path("a.b.c.d")
        self.assertEqual(path.tail(Path("a.b")), Path("c.d"))
        self.assertEqual(path.head(Path("c.d")), Path("a.b"))

    def test_ints(self):
        self.assertEqual(str(Path("1")), "1")
        self.assertEqual(Path("1")[0], 1)
        self.assertEqual(str(Path((1,))), "1")
        self.assertEqual(str(Path("a")+1), "a.1")
        self.assertEqual((Path("a")+1)[1], 1)

    def test_iter_all(self):
        self.assertDictEqual(dict(Path.iter_all(self.mapping, key_cast=str)),
                             {"a": 1, "b.c": 2, "b.d.e": 3, "f.0": 4, "f.1": 5})




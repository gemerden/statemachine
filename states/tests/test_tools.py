import unittest

from states.tools import Path, replace_in_list, has_doubles, state, transition, switch, copy_struct

__author__ = "lars van gemerden"


class TestPath(unittest.TestCase):

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
        self.assertEqual(str(Path("a") + 1), "a.1")
        self.assertEqual((Path("a") + 1)[1], 1)

    def test_iter_all(self):
        self.assertDictEqual(dict(Path.items(self.mapping, key_cast=str)),
                             {"a": 1, "b.c": 2, "b.d.e": 3, "f.0": 4, "f.1": 5})

    def test_add(self):
        assert Path('a') + 'b' + Path('c') == Path('a.b.c')

    def test_splice(self):
        x = 'a.b.c'
        y = 'a.b.d.e'
        common, tail_x, tail_y = Path.splice(x, y)
        assert str(common) == 'a.b'
        assert str(tail_x) == 'c'
        assert str(tail_y) == 'd.e'

        x = 'a.b.c'
        y = 'a.b.c.d'
        common, tail_x, tail_y = Path.splice(x, y)
        assert str(common) == 'a.b.c'
        assert str(tail_x) == ''
        assert str(tail_y) == 'd'

        x = 'a.b.c'
        y = 'a.b.c'
        common, tail_x, tail_y = Path.splice(x, y)
        assert str(common) == 'a.b.c'
        assert str(tail_x) == ''
        assert str(tail_y) == ''

        x = ''
        y = ''
        common, tail_x, tail_y = Path.splice(x, y)
        assert str(common) == ''
        assert str(tail_x) == ''
        assert str(tail_y) == ''

        x = 'a'
        y = 'b'
        common, tail_x, tail_y = Path.splice(x, y)
        assert str(common) == ''
        assert str(tail_x) == 'a'
        assert str(tail_y) == 'b'

    def test_partition(self):
        l, k, r = Path('a.b.c').partition(key='a')
        assert (l, k, r) == (Path(), 'a', Path('b.c'))

        l, k, r = Path('a.b.c').partition(key='b')
        assert (l, k, r) == (Path('a'), 'b', Path('c'))

        l, k, r = Path('a.b.c').partition(key='c')
        assert (l, k, r) == (Path('a.b'), 'c', Path())

        l, k, r = Path('').partition(key='x')
        assert (l, k, r) == (Path(), 'x', Path())

        l, k, r = Path('a.b.c').partition(key='d')
        assert (l, k, r) == (Path('a.b.c'), 'd', Path())


class TestDictClasses(unittest.TestCase):

    def test_basics(self):
        def dummy_state_machine(*args, **kwargs):
            return args, kwargs

        args, kwargs = dummy_state_machine(a=state(), b=state(),
                                           *(transition("a", "b", trigger="t1"),
                                             transition("a", "b", trigger="t2"),
                                             transition("a", switch(a={"condition": "x"}, b={}), trigger="t3")))

        assert len(args) == 3
        assert len(kwargs) == 2

    def test_basics2(self):
        def dummy_state_machine(*args, **kwargs):
            return args, kwargs

        args, kwargs = dummy_state_machine(transition("a", "b", trigger="t1"),
                                           transition("b", "a", trigger="t2"),
                                           transition("a", switch(a={"condition": "x"}, b={}), trigger="t3"),
                                           a=state(), b=state())

        assert len(args) == 3
        assert len(kwargs) == 2


class TestFunctions(unittest.TestCase):

    def test_replace_in_list(self):
        self.assertEqual(replace_in_list([1, 2, 3], 2, [4, 5]), [1, 4, 5, 3])

    def test_has_doubles(self):
        self.assertTrue(has_doubles([1, 2, 3, 2]))
        self.assertFalse(has_doubles([1, 2, 3, 4]))

    def test_copy_struct(self):
        struct = {'a': [1,2,3],
                  'b': (4,5),
                  'c': 'c',
                  'd': {'a': [1,2], 'b': 'skjdfh'}}
        copy = copy_struct(struct)
        assert struct == copy
        assert id(struct['a']) != id(copy['a'])
        assert id(struct['d']) != id(copy['d'])
        assert id(struct['d']['a']) != id(copy['d']['a'])

        def f():
            pass



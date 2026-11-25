"""
The starting throw (owner's rule, 2026-11-16): before the first round each player throws
all five dice and the lowest total goes first; players who tie for the lowest throw again.
"""

import unittest
from unittest import mock

import abaka.engine as engine_module
from abaka.engine import GameEngine
from abaka.models import Category, Die
from abaka.rooms import RoomError, RoomStore


def throws(*totals_or_faces):
    """Fake roll_dice: each argument is one throw, as a total (made of 5 dice) or a list of 5 faces."""
    queue = []
    for t in totals_or_faces:
        if isinstance(t, int):
            faces, rest = [], t
            for left in range(5, 0, -1):  # five faces 1..6 that add up to t
                face = max(1, min(6, rest - (left - 1)))
                faces.append(face)
                rest -= face
        else:
            faces = t
        queue.append([Die(v) for v in faces[:4]] + [Die(faces[4], is_joker=True)])
    return mock.patch.object(engine_module, "roll_dice", side_effect=queue)


class TestEngine(unittest.TestCase):
    def test_lowest_total_starts(self):
        g = GameEngine(["Ann", "Bob", "Cy"], starting_throw=True)
        self.assertTrue(g.choosing_first_player)
        with self.assertRaises(ValueError):
            g.start_turn()  # nobody rolls before the starting throw is over
        with throws(17, 9, 22):
            for expected_thrower in (0, 1, 2):
                self.assertEqual(g.current, expected_thrower)
                g.throw_for_start()
        self.assertFalse(g.choosing_first_player)
        self.assertEqual((g.first_player, g.current), (1, 1))
        self.assertEqual([t["total"] for t in g.starting_throws], [17, 9, 22])
        self.assertEqual(g.dice, [])  # the starting throw is not a turn
        with self.assertRaises(ValueError):
            g.throw_for_start()
        g.start_turn()
        g.record_score(Category.SUM, 0)
        self.assertEqual(g.current, 2)  # play goes round the table from the starter

    def test_a_tie_throws_again_until_one_is_lowest(self):
        g = GameEngine(["Ann", "Bob", "Cy", "Dee"], starting_throw=True)
        with throws(12, 8, 30, 8,   # Bob and Dee tie at 8
                    15, 15,         # tie again
                    20, 11):        # Dee is lowest
            for _ in range(8):
                g.throw_for_start()
        self.assertEqual(g.first_player, 3)
        self.assertEqual(g.current, 3)
        rounds = [(t["round"], t["player"]) for t in g.starting_throws]
        self.assertEqual(rounds, [(1, 0), (1, 1), (1, 2), (1, 3), (2, 1), (2, 3), (3, 1), (3, 3)])

    def test_the_joker_counts_its_face_value(self):
        g = GameEngine(["Ann", "Bob"], starting_throw=True)
        with throws([2, 2, 2, 2, 1], [1, 1, 2, 2, 3]):  # Ann 9 with the joker on 1, Bob 9
            g.throw_for_start()
            g.throw_for_start()
        self.assertEqual([t["total"] for t in g.starting_throws], [9, 9])
        self.assertTrue(g.choosing_first_player)  # a tie: nobody's wild 1 changes the total

    def test_without_the_starting_throw_nothing_changes(self):
        g = GameEngine(["Ann", "Bob"])
        self.assertFalse(g.choosing_first_player)
        g.start_turn()
        self.assertEqual(len(g.dice), 5)


class TestRooms(unittest.TestCase):
    def setUp(self):
        self.store = RoomStore()
        self.code, self.ann = self.store.create("Ann", players=3)
        self.bob = self.store.join(self.code, "Bob", self.store.view(self.code).key)
        self.cy = self.store.join(self.code, "Cy", self.store.view(self.code).key)
        self.tokens = [self.ann, self.bob, self.cy]

    def engine(self):
        return self.store.view(self.code).engine

    def test_each_player_throws_on_their_own_turn(self):
        self.assertTrue(self.engine().choosing_first_player)
        with self.assertRaises(ValueError):
            self.store.roll(self.code, self.ann)  # no rolling before the starting throw
        with self.assertRaises(RoomError):
            self.store.throw_for_start(self.code, self.bob)  # Ann throws first
        version = self.store.version(self.code)
        with throws(14, 21, 10):
            for token in self.tokens:
                self.store.throw_for_start(self.code, token)
        self.assertGreater(self.store.version(self.code), version)
        g = self.engine()
        self.assertEqual((g.first_player, g.current), (2, 2))
        with self.assertRaises(RoomError):
            self.store.throw_for_start(self.code, self.cy)
        with self.assertRaises(RoomError):
            self.store.roll(self.code, self.ann)  # Cy starts
        self.store.roll(self.code, self.cy)

    def test_rematch_opens_with_a_new_starting_throw(self):
        room = self.store._rooms[self.code]
        with throws(14, 21, 10):
            for token in self.tokens:
                self.store.throw_for_start(self.code, token)
        room.engine.is_game_over = lambda: True  # pretend the game finished
        self.store.rematch(self.code, self.bob)
        g = self.engine()
        self.assertTrue(g.choosing_first_player)
        self.assertEqual((g.current, g.starting_throws), (0, []))


if __name__ == "__main__":
    unittest.main()

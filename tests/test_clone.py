"""
GameEngine.clone(): the same game as copy.deepcopy, fully independent, about 20 times cheaper.
Rooms rely on it for copy-on-write and the move picker for trying every move.
"""

import copy
import random
import unittest

from abaka.engine import GameEngine
from abaka.player import PlayerState
from abaka.saving import engine_to_data
from ui_components.moves import cross_options, score_options

IMMUTABLE = (int, float, bool, str, tuple, frozenset, type(None))


def positions(games=12, seed=4):
    """Game states from random games: starting throws, turns with dice, game ends."""
    rng = random.Random(seed)
    random.seed(seed)
    for k in range(games):
        g = GameEngine([f"P{i}" for i in range(2 + k % 4)], starting_throw=k % 2 == 0)
        while g.choosing_first_player:
            yield g
            g.throw_for_start()
        while not g.is_game_over():
            yield g
            g.start_turn()
            if rng.random() < 0.5:
                g.reroll(rng.sample(range(5), rng.randint(1, 5)))
            yield g
            moves = score_options(g) or cross_options(g)
            if rng.random() < 0.2 and cross_options(g):
                moves = cross_options(g)
            move = rng.choice(moves)
            (g.record_cross if move.cross else g.record_score)(move.category, move.slot)
        yield g


def shared_mutables(a, b, path="engine"):
    """Names of mutable attributes that a and b share (must be none)."""
    shared = []
    for name, value in a.__dict__.items():
        other = b.__dict__[name]
        if isinstance(value, IMMUTABLE):
            continue
        if value is other:
            shared.append(f"{path}.{name}")
    return shared


class TestClone(unittest.TestCase):
    def test_same_game_as_deepcopy(self):
        count = 0
        for g in positions():
            self.assertEqual(engine_to_data(g.clone()), engine_to_data(g))
            count += 1
        self.assertGreater(count, 500)

    def test_nothing_mutable_is_shared(self):
        for g in positions(games=4):
            c = g.clone()
            self.assertEqual(set(c.__dict__), set(g.__dict__))
            self.assertEqual(shared_mutables(g, c), [])
            for p, q in zip(g.players, c.players):
                self.assertEqual(set(q.__dict__), set(p.__dict__))
                self.assertEqual(shared_mutables(p, q, "player"), [])
                for cat in p.table:
                    self.assertIsNot(p.table[cat], q.table[cat])
            for d, e in zip(g.dice, c.dice):
                self.assertIsNot(d, e)
            for t, u in zip(g.starting_throws, c.starting_throws):
                self.assertIsNot(t, u)
                self.assertIsNot(t["dice"], u["dice"])

    def test_changing_the_clone_never_changes_the_original(self):
        for g in positions(games=6, seed=8):
            before = engine_to_data(g)
            c = g.clone()
            if c.choosing_first_player:
                c.throw_for_start()
            elif c.is_game_over():
                c.players[0].table[next(iter(c.players[0].table))][0] = 999
            elif not c.dice:
                c.start_turn()
            else:
                if c.rolls_left:
                    c.reroll([0, 1, 2, 3, 4])
                move = (score_options(c) or cross_options(c))[0]
                (c.record_cross if move.cross else c.record_score)(move.category, move.slot)
            c.row_bonus_claimed.clear()
            c.col_bonus_claimed.append(True)
            c.starting_throws.append({"round": 9, "player": 0, "dice": [], "total": 0})
            self.assertEqual(engine_to_data(g), before)

    def test_move_previews_match_deepcopy(self):
        """score_options tries every row on a clone; the results equal trials on deep copies."""
        checked = 0
        for g in positions(games=6, seed=2):
            if not g.dice:
                continue
            via_clone = [(m.category, m.slot, m.value, m.balance_change, m.bonus_lost) for m in score_options(g)]
            reference = []
            for m in score_options(g):
                trial = copy.deepcopy(g)
                trial.record_score(m.category, m.slot)
                reference.append((m.category, m.slot, trial.players[g.current].table[m.category][m.slot],
                                  m.balance_change, m.bonus_lost))
            self.assertEqual(via_clone, reference)
            checked += 1
        self.assertGreater(checked, 100)

    def test_player_clone(self):
        p = PlayerState("Ann")
        p.school_balance_loc = (next(iter(p.table)), 0)
        q = p.clone()
        q.column_bonus[0] = 5
        next(iter(q.table.values()))[0] = 7
        self.assertEqual(p.column_bonus[0], None)
        self.assertIsNone(next(iter(p.table.values()))[0])


if __name__ == "__main__":
    unittest.main()

"""
The computer's final dice stay on the table (owner, Backlog item 35: "you should see his final
combination first"): the engine keeps the dice the latest move was written from, abaka/turns.py
says when they are shown and with what words, the page draws them in place of the empty dice
until the next player rolls, and the API sends them to apps. With several computers, the next
one waits before it rolls.
"""

import os
import random
import unittest
from unittest import mock

import abaka.rooms as rooms
import code_version
from abaka import api, bot
from abaka.engine import GameEngine
from abaka.i18n import set_language
from abaka.models import Category as C
from abaka.models import Die
from abaka.moves import cross_options, score_options
from abaka.rooms import RoomStore
from abaka.saving import engine_from_data, engine_to_data
from abaka.turns import last_throw, what_was_written

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # the base Python 3.8
    AppTest = None

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "abaka_ui.py")


def throw(engine, values, joker):
    """The current player rolls exactly these dice (four normal ones and the joker)."""
    engine.start_turn()
    engine.dice = [Die(v) for v in values] + [Die(joker, is_joker=True)]


class Clock:
    def __init__(self):
        self.now = 1_800_000_000.0

    def __call__(self):
        return self.now


class TestTheEngine(unittest.TestCase):
    def test_the_dice_of_the_latest_move_are_kept(self):
        g = GameEngine(["Ann", "Hal"])
        self.assertEqual(g.last_dice, ())
        throw(g, [6, 6, 5, 5], 5)
        g.record_score(C.FULL, 0)
        self.assertEqual(g.last_dice, ((6, False), (6, False), (5, False), (5, False), (5, True)))
        self.assertEqual(g.dice, [])
        throw(g, [1, 2, 3, 4], 6)
        g.record_cross(C.ABAKA, 0)
        self.assertEqual(g.last_dice, ((1, False), (2, False), (3, False), (4, False), (6, True)))

    def test_saved_loaded_and_shared_by_a_clone(self):
        g = GameEngine(["Ann", "Hal"])
        throw(g, [6, 6, 5, 5], 5)
        g.record_score(C.FULL, 0)
        self.assertEqual(engine_from_data(engine_to_data(g)).last_dice, g.last_dice)
        clone = g.clone()
        throw(clone, [1, 1, 1, 1], 1)
        clone.record_score(C.ABAKA, 0)
        self.assertEqual(g.last_dice[0], (6, False))  # the copy's move is not the game's
        data = engine_to_data(g)
        del data["last_dice"]  # a game saved before
        self.assertEqual(engine_from_data(data).last_dice, ())


class TestLastThrow(unittest.TestCase):
    def setUp(self):
        self.addCleanup(set_language, "en")

    def test_the_computers_dice_stay_until_the_next_player_rolls(self):
        g = GameEngine(["Ann", "Computer"])
        throw(g, [2, 2, 3, 4], 6)
        g.record_score(C.PAIR, 0)
        self.assertIsNone(last_throw(g, [1]))  # a person's move: everyone saw it made
        throw(g, [6, 6, 5, 5], 5)  # the computer's
        self.assertIsNone(last_throw(g, [1]))  # its dice are the dice on the table
        g.record_score(C.FULL, 0)
        shown = last_throw(g, [1])
        self.assertEqual(shown["seat"], 1)
        self.assertEqual(shown["dice"], [(6, False), (6, False), (5, False), (5, False), (5, True)])
        self.assertEqual(shown["text"], "Computer’s last throw: scored 54 in Full house")
        set_language("ru")
        self.assertEqual(last_throw(g, [1])["text"], "Последний бросок — Computer: 54 в «Фулл-хаус»")
        set_language("en")
        self.assertIsNone(last_throw(g, []))  # no computer in this game
        g.start_turn()
        self.assertIsNone(last_throw(g, [1]))  # Ann rolled: her dice now

    def test_a_crossed_out_row_and_a_school_row_in_words(self):
        g = GameEngine(["Computer", "Ann"])
        throw(g, [1, 2, 3, 4], 6)
        g.record_cross(C.ABAKA, 0)
        self.assertEqual(last_throw(g, [0])["text"], "Computer’s last throw: crossed out Abaka")
        self.assertEqual(what_was_written(g, g.last_move), "crossed out Abaka")

    def test_nothing_before_a_move_during_the_starting_throw_or_after_the_game(self):
        self.assertIsNone(last_throw(GameEngine(["Ann", "Computer"]), [1]))
        self.assertIsNone(last_throw(GameEngine(["Ann", "Computer"], starting_throw=True), [1]))
        random.seed(6)
        g = GameEngine(["Ann", "Computer"])
        while not g.is_game_over():
            g.start_turn()
            move = (score_options(g) + cross_options(g))[0]
            (g.record_cross if move.cross else g.record_score)(move.category, move.slot)
        self.assertEqual(g.last_move[0], 1)
        self.assertTrue(g.last_dice)
        self.assertIsNone(last_throw(g, [1]))  # the results are on the screen
        old = engine_to_data(GameEngine(["Ann", "Computer"]))
        del old["last_dice"]
        self.assertIsNone(last_throw(engine_from_data(old), [1]))


class TestInARoom(unittest.TestCase):
    def play_until_the_computer_has_moved(self, store, code, token):
        """The person's seats play plain moves; the computer plays its own. Returns the view after its move."""
        for _ in range(400):
            view = store.view(code)
            engine = view.engine
            if engine.last_move is not None and engine.last_move[0] in view.computers and not engine.dice:
                return view
            if engine.current in view.computers:
                store.seen(code)
            elif engine.choosing_first_player:
                store.throw_for_start(code, token)
            elif not engine.dice:
                store.roll(code, token)
            else:
                move = (score_options(engine) + cross_options(engine))[0]
                (store.cross if move.cross else store.score)(code, token, move.category, move.slot)
        self.fail("the computer made no move")

    def test_the_api_sends_the_throw_until_the_player_rolls(self):
        store = RoomStore(computer_pace=0)
        made = api.handle({"op": "create_local", "names": ["Ann", ""], "computers": [1]}, store)
        code, token = made["code"], made["token"]
        self.assertIsNone(made["state"]["last_throw"])
        view = self.play_until_the_computer_has_moved(store, code, token)
        state = api.handle({"op": "state", "code": code, "token": token, "lang": "ru"}, store)["state"]
        shown = state["last_throw"]
        self.assertEqual(shown["seat"], 1)
        self.assertEqual(shown["dice"], [{"value": v, "joker": j} for v, j in view.engine.last_dice])
        self.assertTrue(shown["text"].startswith("Последний бросок — Компьютер: ") or
                        shown["text"].startswith("Последний бросок — Computer: "), shown["text"])
        self.assertIn("roll", state["can"])  # the one button that moves on
        state = api.handle({"op": "roll", "code": code, "token": token, "version": state["version"]}, store)["state"]
        self.assertIsNone(state["last_throw"])

    def test_the_next_computer_waits_while_the_first_ones_dice_are_read(self):
        clock = Clock()
        with mock.patch.object(rooms.time, "time", clock):
            store = RoomStore()  # the real pace
            code, token = store.create_local(["Ann", "Hal", "Eve"], computers=[1, 2])

            def step():
                clock.now += rooms.COMPUTER_PACE_SECONDS + 0.01
                store.seen(code)

            for _ in range(400):  # until one computer has moved and the other is to roll
                view = store.view(code)
                engine = view.engine
                if (engine.last_move is not None and engine.last_move[0] in (1, 2) and not engine.dice
                        and engine.current in (1, 2)):
                    break
                if engine.current in (1, 2):
                    step()
                elif engine.choosing_first_player:
                    store.throw_for_start(code, token)
                elif not engine.dice:
                    store.roll(code, token)
                else:
                    move = (score_options(engine) + cross_options(engine))[0]
                    (store.cross if move.cross else store.score)(code, token, move.category, move.slot)
            else:
                self.fail("two computers never played one after the other")
            version = store.view(code).version
            self.assertIsNotNone(last_throw(store.view(code).engine, (1, 2)))
            step()  # a usual pace later: the first one's dice are still being read
            self.assertEqual(store.view(code).version, version)
            clock.now += rooms.COMPUTER_PACE_SECONDS * (rooms.COMPUTER_REST_PACES - 1)
            store.seen(code)
            self.assertEqual(store.view(code).version, version + 1)  # now it rolls
            self.assertTrue(store.view(code).engine.dice)


@unittest.skipIf(AppTest is None, "Streamlit is not installed")
class TestThePage(unittest.TestCase):
    def test_the_dice_stay_on_the_page_until_roll_dice(self):
        from streamlit.testing.v1 import element_tree
        if not hasattr(element_tree.ButtonGroup, "_is_single_select"):  # AppTest 1.48: single-choice groups
            group_value = element_tree.ButtonGroup.value.fget

            def one_or_more(group):
                value = group_value(group)
                return [] if value is None else value if isinstance(value, list) else [value]

            patcher = mock.patch.object(element_tree.ButtonGroup, "value", property(one_or_more))
            patcher.start()
            self.addCleanup(patcher.stop)
        env = mock.patch.dict(os.environ, {"ABAKA_SAVE_DIR": ""})
        env.start()
        self.addCleanup(env.stop)
        stores = []

        class FreshRoomStore(rooms.RoomStore):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                stores.append(self)

        self.addCleanup(setattr, rooms, "RoomStore", rooms.RoomStore)
        rooms.RoomStore = FreshRoomStore
        code_version.mark_current()
        AppTest.from_file(APP, default_timeout=30).run()  # the app makes its store
        store = stores[-1]
        store.computer_pace = 0
        code, token = store.create_local(["Ann", "<b>Hal</b>"], computers=[1])
        view = TestInARoom.play_until_the_computer_has_moved(self, store, code, token)
        store.computer_pace = 1e9  # the page's own checks make no step
        self.assertEqual(view.engine.current, 0)
        at = AppTest.from_file(APP, default_timeout=30)
        at.query_params["room"] = code
        at.session_state["room_code"], at.session_state["seat_token"] = code, token
        at.run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        html = "".join(h.proto.body for h in at.get("html"))
        self.assertIn('<div class="ab-last-throw">', html)
        self.assertIn("&lt;b&gt;Hal&lt;/b&gt;’s last throw: ", html)  # a name is text, never markup
        dice = [b for b in at.button if (b.key or "").startswith("die-")]
        self.assertEqual(len(dice), 5)
        self.assertTrue(all(b.disabled for b in dice))  # the computer's dice: nothing to pick
        self.assertEqual([b.label.split(" ")[0] for b in dice], [str(v) for v, _ in view.engine.last_dice])
        at.button(key="roll").click()  # one button: on to the player's turn, and their roll
        at.run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        self.assertNotIn("ab-last-throw", "".join(h.proto.body for h in at.get("html") if "<style>" not in h.proto.body))
        self.assertTrue(store.view(code).engine.dice)
        self.assertTrue(any(not b.disabled for b in at.button if (b.key or "").startswith("die-")))


if __name__ == "__main__":
    unittest.main()

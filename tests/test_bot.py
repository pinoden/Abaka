"""
The computer player (abaka/bot.py, Backlog item 33): it plays only moves the rules offer,
finishes whole games, plays better than a random and a greedy player, and decides fast.
In a room (abaka/rooms.py) it plays its seats through the store, a step at a time, paced so
a person sees each one, never twice for one step, across saving and loading, and through the
API. The web page draws its turn without buttons for anyone else.
"""

import functools
import os
import random
import tempfile
import threading
import time
import unittest
from unittest import mock

import abaka.rooms as rooms
from abaka import bot
from abaka.api import ApiError, handle
from abaka.clubs import ClubStore
from abaka.engine import GameEngine
from abaka.i18n import set_language
from abaka.models import Category, Die
from abaka.moves import cross_options, score_options
from abaka.rooms import RoomError, RoomStore

import code_version

try:
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    from streamlit.testing.v1 import element_tree
except ImportError:  # the base Python 3.8
    AppTest = None

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "abaka_ui.py")


def set_dice(engine, values, joker):
    """Put these dice on the table (four normal ones and the joker's value), as a first roll."""
    engine.dice = [Die(v) for v in values] + [Die(joker, is_joker=True)]
    engine.rolls_left, engine.first_roll = 2, True


def play_game(policies, seed):
    """One game on GameEngine, each seat by its policy; returns the engine at the end."""
    random.seed(seed)
    rng = random.Random(seed)
    engine = GameEngine([f"P{i}" for i in range(len(policies))], starting_throw=True)
    while not engine.is_game_over():
        bot.apply_step(engine, policies[engine.current](engine, rng))
    return engine


def computer(engine, rng):
    return bot.next_step(engine)


class TestDecisions(unittest.TestCase):
    def test_every_step_is_one_the_rules_offer(self):
        for players in (2, 3, 5):
            random.seed(players)
            engine = GameEngine([f"P{i}" for i in range(players)], starting_throw=True)
            steps = 0
            while not engine.is_game_over():
                step = bot.next_step(engine)
                if step[0] == "reroll":
                    self.assertGreater(engine.rolls_left, 0)
                    self.assertTrue(step[1])
                    self.assertEqual(len(set(step[1])), len(step[1]))
                    self.assertTrue(all(0 <= i < 5 for i in step[1]))
                elif step[0] in ("score", "cross"):
                    offered = score_options(engine) if step[0] == "score" else cross_options(engine)
                    self.assertIn((step[1], step[2]), [(m.category, m.slot) for m in offered])
                bot.apply_step(engine, step)  # the engine refuses anything else
                steps += 1
            self.assertGreaterEqual(steps, 45 * players * 2)  # at least a roll and a move per cell

    def test_it_keeps_dice_toward_what_is_still_open(self):
        engine = GameEngine(["Bot", "Ann"])
        set_dice(engine, [6, 6, 6, 2], 3)  # three sixes: Kare, Abaka and School 6 are open
        engine.rolls_left, engine.first_roll = 1, False  # (on the first roll, Sum doubled is worth taking)
        step = bot.next_step(engine)
        self.assertEqual(step[0], "reroll")
        rolled = sorted(engine.dice[i].value for i in step[1])
        self.assertNotIn(6, rolled)  # keeps the sixes

    def test_a_great_first_roll_is_written_at_once(self):
        engine = GameEngine(["Bot", "Ann"])
        set_dice(engine, [5, 5, 5, 5], 5)  # Abaka on the first roll: 2 x (25 + 50)
        self.assertEqual(bot.next_step(engine), ("score", Category.ABAKA, 0))

    def test_it_crosses_out_where_least_is_lost(self):
        engine = GameEngine(["Bot", "Ann"])
        me = engine.players[0]
        # A board where only Abaka and Large straight are left among the combinations, nothing
        # scores, and the balance cannot pay: Abaka's cell is worth least.
        for c in Category:
            me.table[c][:3] = ["X", "X", "X"] if c.name.startswith("SCHOOL") else [10, 10, 10]
        me.table[Category.ABAKA][:3] = [None, None, None]
        me.table[Category.LARGE_STRAIGHT][:3] = [20, None, None]
        me.table[Category.SCHOOL_6][:3] = [None, None, None]
        set_dice(engine, [1, 1, 2, 3], 4)
        engine.rolls_left, engine.first_roll = 0, False
        options = score_options(engine)
        self.assertEqual(options, [], options)  # nothing scores
        self.assertEqual(bot.next_step(engine), ("cross", Category.ABAKA, 0))

    def test_school_payments_never_drive_the_balance_below_zero_when_avoidable(self):
        engine = GameEngine(["Bot", "Ann"])
        me = engine.players[0]
        for c in Category:
            me.table[c][:3] = [10, 10, 10] if not c.name.startswith("SCHOOL") else ["X", "X", "X"]
        me.table[Category.SUM][:3] = [20, 20, None]  # one combination cell left
        me.table[Category.SCHOOL_5][:3] = ["X", "X", None]  # and one School cell
        me.school_balance = 4
        set_dice(engine, [1, 2, 3, 4], 6)
        engine.rolls_left, engine.first_roll = 0, False
        # Paying in School 5 is refused (balance 4, needs 10). Sum must be written; then School 5
        # comes last. Writing Sum now keeps the game going without a negative balance yet.
        self.assertEqual(bot.next_step(engine), ("score", Category.SUM, 2))

    def test_whole_games_for_two_to_five_players(self):
        for players in range(2, 6):
            with self.subTest(players=players):
                engine = play_game([computer] * players, seed=100 + players)
                self.assertTrue(engine.is_game_over())
                scores = [p.calculate_score() for p in engine.players]
                self.assertGreater(sum(scores) / players, 300, scores)

    def test_it_beats_a_random_and_a_greedy_player(self):
        for other in (bot.random_step, bot.greedy_step):
            with self.subTest(other=other.__name__):
                ours, theirs = [], []
                for n in range(4):
                    seats = [computer, other] if n % 2 == 0 else [other, computer]
                    engine = play_game(seats, seed=200 + n)
                    scores = [p.calculate_score() for p in engine.players]
                    me = 0 if n % 2 == 0 else 1
                    ours.append(scores[me])
                    theirs.append(scores[1 - me])
                self.assertGreater(min(a - b for a, b in zip(ours, theirs)), 0, (ours, theirs))

    def test_a_decision_takes_well_under_100_ms(self):
        bot.tables()
        random.seed(5)
        engine = GameEngine(["A", "B"])
        took = []
        while not engine.is_game_over() and len(took) < 60:
            started = time.perf_counter()
            step = bot.next_step(engine)
            if step[0] not in ("throw", "roll"):
                took.append(time.perf_counter() - started)
            bot.apply_step(engine, step)
        took.sort()
        self.assertLess(took[len(took) // 2], 0.1, took)

    def test_names_for_the_computer(self):
        set_language("en")
        self.assertEqual(bot.computer_names(["Ann", ""], [1]), ["Ann", "Computer"])
        self.assertEqual(bot.computer_names(["Ann", "", ""], [1, 2]), ["Ann", "Computer 1", "Computer 2"])
        self.assertEqual(bot.computer_names(["Ann", "Hal"], [1]), ["Ann", "Hal"])
        set_language("ru")
        try:
            self.assertEqual(bot.computer_names(["", ""], [0]), ["Компьютер", ""])
        finally:
            set_language("en")


class Clock:
    """time.time() for the store, moved on by hand."""

    def __init__(self):
        self.now = 1_800_000_000.0

    def __call__(self):
        return self.now


class TestInARoom(unittest.TestCase):
    def store(self, **kwargs):
        return RoomStore(**kwargs)

    def finish(self, store, code, token, polls=20000):
        """Play the people's seats (with the computer's choices) and poll for the computer's."""
        for _ in range(polls):
            view = store.view(code)
            engine = view.engine
            if engine.is_game_over():
                return view
            if engine.current in view.computers:
                store.seen(code)
                continue
            step = bot.next_step(engine)
            kind, v = step[0], view.version
            if kind == "throw":
                store.throw_for_start(code, token, v)
            elif kind == "roll":
                store.roll(code, token, v)
            elif kind == "reroll":
                store.reroll(code, token, step[1], v)
            elif kind == "score":
                store.score(code, token, step[1], step[2], v)
            else:
                store.cross(code, token, step[1], step[2], v)
        self.fail("the game did not end")

    def test_whole_games_with_computers_for_two_to_five_players(self):
        store = self.store(computer_pace=0)
        for players in range(2, 6):
            with self.subTest(players=players):
                computers = list(range(1, players))
                code, token = store.create_local(bot.computer_names(["Ann"] + [""] * (players - 1), computers),
                                                 computers=computers)
                view = self.finish(store, code, token)
                self.assertEqual(view.computers, tuple(computers))
                self.assertEqual(view.names[1], "Computer" if players == 2 else "Computer 1")
                self.assertEqual(len(view.results), 1)

    def test_people_cannot_move_for_the_computer(self):
        store = self.store(computer_pace=0)
        code, token = store.create_local(["Ann", "Hal"], computers=[1])
        for _ in range(50):
            engine = store.view(code).engine
            if engine.current == 1:
                break
            store.throw_for_start(code, token) if engine.choosing_first_player else None
            if not engine.choosing_first_player:
                store.roll(code, token)
                move = score_options(store.view(code).engine)[0]
                store.score(code, token, move.category, move.slot)
        self.assertEqual(store.view(code).engine.current, 1)
        with self.assertRaisesRegex(RoomError, "computer's turn"):
            if store.view(code).engine.choosing_first_player:
                store.throw_for_start(code, token)
            else:
                store.roll(code, token)

    def test_the_computer_waits_a_moment_between_steps(self):
        clock = Clock()
        with mock.patch.object(rooms.time, "time", clock):
            store = self.store()  # the real pace
            code, token = store.create_local(["Hal", "Ann"], computers=[0])
            engine = store.view(code).engine
            self.assertEqual(engine.current, 0)  # Hal throws first in the starting throw
            clock.now += 0.5
            self.assertEqual(store.seen(code)[0], 0)  # too soon: nothing yet
            clock.now += 0.6
            self.assertEqual(store.seen(code)[0], 1)  # its throw
            self.assertEqual(store.seen(code)[0], 1)  # not again at once
            self.assertEqual(len(store.view(code).engine.starting_throws), 1)
            # Ann throws; play on until the computer's turn shows the dice it keeps.
            steps, picked = [], None
            for _ in range(400):
                view = store.view(code)
                if view.engine.current != 0:
                    if view.engine.choosing_first_player:
                        store.throw_for_start(code, token)
                    elif not view.engine.dice:
                        store.roll(code, token)
                    else:
                        move = (score_options(view.engine) + cross_options(view.engine))[0]
                        (store.cross if move.cross else store.score)(code, token, move.category, move.slot)
                    continue
                clock.now += rooms.COMPUTER_PACE_SECONDS
                before = store.view(code)
                store.seen(code)
                after = store.view(code)
                if after.picked and not before.picked:
                    picked = (before.version, after.picked, after.engine.dice)
                    break
                steps.append(after.version - before.version)
            self.assertIsNotNone(picked, "the computer never kept some dice and rolled the others")
            self.assertTrue(all(step == 1 for step in steps), steps)  # one move per due poll
            version, shown, dice = picked
            self.assertEqual(store.view(code).version, version)  # showing the dice is not a move
            clock.now += 0.5
            store.seen(code)
            self.assertEqual(store.view(code).version, version)  # not yet
            clock.now += 0.6
            store.seen(code)
            after = store.view(code)
            self.assertEqual(after.version, version + 1)
            self.assertEqual(after.rerolled, shown)  # exactly the dice it showed
            self.assertEqual(after.picked, ())
            kept = [i for i in range(5) if i not in shown]
            self.assertEqual([(after.engine.dice[i].value) for i in kept], [dice[i].value for i in kept])

    def test_two_pages_never_make_it_play_twice(self):
        clock = Clock()
        with mock.patch.object(rooms.time, "time", clock):
            store = self.store()
            code, token = store.create_local(["Hal", "Ann"], computers=[0])
            slow = bot.next_step

            def thinking(engine):
                time.sleep(0.05)  # while one page works out the step, the others poll
                return slow(engine)

            with mock.patch.object(bot, "next_step", thinking):
                for _ in range(6):
                    clock.now += 1.1
                    if store.view(code).engine.current != 0:
                        break
                    before = store.view(code)
                    threads = [threading.Thread(target=store.seen, args=(code,)) for _ in range(8)]
                    for thread in threads:
                        thread.start()
                    for thread in threads:
                        thread.join()
                    after = store.view(code)
                    moved = after.version - before.version + (after.seen[1] - before.seen[1])
                    self.assertEqual(moved, 1, "one step per due moment, however many pages poll")

    def test_a_saved_game_with_the_computer_loads_and_goes_on(self):
        with tempfile.TemporaryDirectory() as folder:
            store = RoomStore(save_dir=folder, computer_pace=0)
            code, token = store.create_local(["Ann", "Hal"], computers=[1])
            for _ in range(30):
                store.seen(code)
                engine = store.view(code).engine
                if engine.current == 0 and engine.choosing_first_player:
                    store.throw_for_start(code, token)
                elif engine.current == 0:
                    break
            store.retire()
            again = RoomStore(save_dir=folder, computer_pace=0)
            view = again.view(code)
            self.assertEqual(view.computers, (1,))
            self.assertEqual(again.resume_local(code, view.key), token)
            self.finish(again, code, token)

    def test_computer_games_do_not_count_for_clubs(self):
        store = self.store()
        with self.assertRaisesRegex(RoomError, "do not count for a club"):
            store.create_local(["Ann", "Hal"], club="K7PX2M", computers=[1])
        with self.assertRaisesRegex(RoomError, "must be a person"):
            store.create_local(["Hal", "Eve"], computers=[0, 1])
        with self.assertRaisesRegex(RoomError, "does not exist"):
            store.create_local(["Ann", "Hal"], computers=[2])

    def test_a_fault_in_the_bot_never_stops_the_game(self):
        store = self.store(computer_pace=0)
        code, token = store.create_local(["Hal", "Ann"], computers=[0])
        with mock.patch.object(bot, "next_step", side_effect=ZeroDivisionError("a bug")), \
                self.assertLogs("abaka", "WARNING"):
            store.seen(code)
        self.assertEqual(len(store.view(code).engine.starting_throws), 1)  # a plain step instead


class TestApi(unittest.TestCase):
    def setUp(self):
        self.store = RoomStore(computer_pace=0)
        self.clubs = ClubStore()

    def call(self, **request):
        return handle(request, self.store, self.clubs)

    def test_a_game_against_the_computer(self):
        made = self.call(op="create_local", names=["Ann", ""], computers=[1], lang="ru")
        state = made["state"]
        self.assertEqual(state["names"], ["Ann", "Компьютер"])
        self.assertEqual(state["computers"], [1])
        code, token = made["code"], made["token"]
        turns = 0
        while state["phase"] != "over":
            game = state["game"]
            if game["current"] == 1:
                self.assertEqual([c for c in state["can"] if c not in ("react", "say")], [])
                self.assertIsNone(state["moves"])
                self.call(op="seen", code=code, token=token)  # a poll lets the computer play
            elif "throw" in state["can"]:
                self.call(op="throw", code=code, token=token, version=state["version"])
            elif "roll" in state["can"]:
                self.call(op="roll", code=code, token=token, version=state["version"])
            else:
                move = state["moves"]["score"][0] if state["moves"]["score"] else state["moves"]["cross"][0]
                op = "score" if state["moves"]["score"] else "cross"
                self.call(op=op, code=code, token=token, version=state["version"], row=move["row"])
                turns += 1
            state = self.call(op="state", code=code, token=token)["state"]
        self.assertEqual(turns, 45)  # Ann's cells; the computer filled its own
        self.assertTrue(all(v is not None for row in state["game"]["players"][1]["rows"].values()
                            for v in row[:3]))

    def test_refusals(self):
        for computers in ("1", [5], [True], [0.5]):
            with self.assertRaises(ApiError) as e:
                self.call(op="create_local", names=["Ann", ""], computers=computers)
            self.assertEqual(e.exception.code, "bad_request")
        with self.assertRaises(ApiError) as e:
            self.call(op="create_local", names=["", ""], computers=[0, 1])
        self.assertEqual(e.exception.code, "refused")
        club = self.call(op="create_club", name="Friday")["club"]["code"]
        with self.assertRaises(ApiError) as e:
            self.call(op="create_local", names=["Ann", ""], computers=[1], club=club)
        self.assertEqual(e.exception.code, "refused")

    def test_games_without_the_computer_say_so(self):
        state = self.call(op="create_local", names=["Ann", "Bob"])["state"]
        self.assertEqual(state["computers"], [])


@unittest.skipIf(AppTest is None, "Streamlit is not installed")
class TestThePage(unittest.TestCase):
    def setUp(self):
        env = mock.patch.dict(os.environ, {"ABAKA_SAVE_DIR": ""})
        env.start()
        self.addCleanup(env.stop)
        self.stores = []
        stores = self.stores

        class FreshRoomStore(rooms.RoomStore):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                stores.append(self)

        self.addCleanup(setattr, rooms, "RoomStore", rooms.RoomStore)
        rooms.RoomStore = FreshRoomStore
        code_version.mark_current()
        self.polls = []
        polls, fragment = self.polls, st.fragment

        def recording_fragment(func=None, *, run_every=None, **kwargs):
            def decorate(f):
                @functools.wraps(f)
                def run(*args, **kw):
                    polls.append(run_every)
                    return f(*args, **kw)
                return fragment(run, run_every=run_every, **kwargs)
            return decorate if func is None else decorate(func)

        patcher = mock.patch.object(st, "fragment", recording_fragment)
        patcher.start()
        self.addCleanup(patcher.stop)
        if not hasattr(element_tree.ButtonGroup, "_is_single_select"):  # AppTest 1.48 (test_ui_reruns.py)
            group_value = element_tree.ButtonGroup.value.fget

            def one_or_more(group):
                try:
                    value = group_value(group)
                except KeyError:  # a group the page has not reported yet: its default
                    value = group.proto.default and [group.options[i] for i in group.proto.default]
                return [] if value is None else value if isinstance(value, list) else [value]

            patcher = mock.patch.object(element_tree.ButtonGroup, "value", property(one_or_more))
            patcher.start()
            self.addCleanup(patcher.stop)

    def run_page(self, at):
        at.run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        return at

    def test_a_game_against_the_computer_from_the_home_page(self):
        at = self.run_page(AppTest.from_file(APP, default_timeout=30))
        store = self.stores[0]
        if hasattr(element_tree.ButtonGroup, "_is_single_select"):
            control = next(c for c in at.button_group if c.key == "local_computers_2")
            control.set_value(1)
            self.run_page(at)
            self.assertEqual([b.label for b in at.text_input if b.key.startswith("local_p")], ["Player 1"])
            at.text_input(key="local_p1").input("Ann")
            next(b for b in at.button if b.label == "Start game").click()
            self.run_page(at)
            code = at.session_state["room_code"]
        else:  # AppTest 1.48 cannot set a segmented control the page has not used yet: the game as the card makes it
            code, token = store.create_local(["Ann", "Computer"], computers=[1])
            at = AppTest.from_file(APP, default_timeout=30)
            at.query_params["room"] = code
            at.session_state["room_code"], at.session_state["seat_token"] = code, token
            self.run_page(at)
        view = store.view(code)
        self.assertEqual(view.names, ["Ann", "Computer"])
        self.assertEqual(view.computers, (1,))
        store.computer_pace = 1e9  # the page's own checks make no step: the test makes them

        def computer_step():
            store.computer_pace = 0
            store.seen(code)
            store.computer_pace = 1e9

        for _ in range(40):  # Ann throws; the computer throws when the page checks the room
            engine = store.view(code).engine
            if not engine.choosing_first_player:
                break
            if engine.current == 0:
                at.button(key="start-throw").click()
                self.run_page(at)
            else:
                computer_step()
                self.run_page(at)
        engine = store.view(code).engine
        if engine.current == 0:  # Ann goes first: play her turn
            at.button(key="roll").click()
            self.run_page(at)
            move = score_options(store.view(code).engine)[0]
            store.score(code, at.session_state["seat_token"], move.category, move.slot)
            self.run_page(at)
        self.assertEqual(store.view(code).engine.current, 1)
        # The computer's turn: no buttons to play it, a mark on the turn, quick checks of the room.
        self.assertFalse([b for b in at.button if b.key in ("roll", "start-throw", "confirm")])
        self.assertIn("computer", " ".join(h.proto.body for h in at.get("html")))
        self.assertEqual(self.polls[-1], 0.5)
        for _ in range(10):
            if store.view(code).engine.current == 0:
                break
            computer_step()
        self.assertEqual(store.view(code).engine.current, 0)
        self.run_page(at)
        self.assertTrue(at.button(key="roll"))
        self.assertIn("Last move:", " ".join(h.proto.body for h in at.get("html")) +
                      " ".join(c.value for c in at.caption))
        self.assertEqual(self.polls[-1], 10.0)


if __name__ == "__main__":
    unittest.main()
